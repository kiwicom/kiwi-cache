import asyncio
from datetime import timedelta, datetime

import logging
import aioredis

from . import json
from .helpers import CallAttempt, CallAttemptException


class AioKiwiCache:  # pylint: disable=too-many-instance-attributes
    """Caches data from expensive sources to Redis and to memory."""

    instances = []  # type: List[AioKiwiCache]
    reload_ttl = timedelta(minutes=1)
    cache_ttl = reload_ttl * 10
    refill_lock_ttl = timedelta(seconds=5)
    resources_redis = None

    def __init__(self, resources_redis=None, logger=None, statsd=None):
        # type: (redis.Connection, logging.Logger, datadog.DogStatsd) -> None

        self.instances.append(self)

        if resources_redis is not None:
            self.resources_redis = resources_redis

        self.check_initialization()

        self.name = self.__class__.__name__
        self.expires_at = datetime.utcnow()
        self._data = {}  # type: dict
        self.logger = logger if logger else logging.getLogger(__name__)
        self.statsd = statsd
        self.call_attempt = CallAttempt("{}.load_from_source".format(self.name.lower()))
        self.initialized = False

    def check_initialization(self):
        if self.resources_redis is None:
            raise RuntimeError('You must set a redis.Connection object')

        if self.cache_ttl < self.reload_ttl:
            raise RuntimeError('The cache_ttl has to be greater then reload_ttl.')

    async def acheck_initialization(self):
        if await self.resources_redis.ttl(self.redis_key) > int(self.reload_ttl.total_seconds()):
            await self.resources_redis.expire(self.redis_key, int(self.reload_ttl.total_seconds()))

    @property
    def redis_key(self):
        return 'resource:' + self.name

    async def getitem(self, key):
        return (await self.get_data())[key]

    async def get(self, key, default=None):
        return (await self.get_data()).get(key, default)

    async def contains(self, key):
        return key in await self.get_data()

    async def keys(self):
        return (await self.get_data()).keys()

    async def values(self):
        return (await self.get_data()).values()

    async def items(self):
        return (await self.get_data()).items()

    async def get_data(self):
        await self.maybe_reload()
        return self._data

    async def load_from_source(self):  # type: () -> dict
        """Get the full data bundle from our expensive source."""
        raise NotImplementedError()

    async def load_from_cache(self):  # type: () -> str
        """Get the full data bundle from cache."""
        return await self.resources_redis.get(self.redis_key)

    async def save_to_cache(self, data):  # type: (dict) -> None
        """Save the provided full data bundle to cache."""
        try:
            await self.resources_redis.set(
                self.redis_key, json.dumps(data), expire=int(self.cache_ttl.total_seconds()) if self.cache_ttl else 0
            )
        except aioredis.RedisError:
            self.statsd and self.statsd.increment('kiwicache', tags=['name:' + self.name, 'status:redis_error'])
            self.logger.exception("kiwicache.redis_exception")

    async def reload(self):
        """Load the full data bundle, from cache, or if unavailable, from source."""
        try:
            cache_data = await self.load_from_cache()
        except aioredis.RedisError:
            self.logger.exception("kiwicache.redis_exception")
            self.statsd and self.statsd.increment('kiwicache', tags=['name:' + self.name, 'status:redis_error'])
            return

        if cache_data:
            self._data = json.loads(cache_data)
            self.expires_at = datetime.utcnow() + self.reload_ttl
            self.statsd and self.statsd.increment('kiwicache', tags=['name:' + self.name, 'status:success'])
        else:
            await self.refill_cache()
            await self.reload()

    async def maybe_reload(self):  # type: () -> None
        """Load the full data bundle if it's too old."""
        if not self.initialized:
            await self.acheck_initialization()
            self.initialized = True

        if not self._data or self.expires_at < datetime.utcnow():
            try:
                await self.reload()
            except CallAttemptException:
                raise
            except Exception:
                self.logger.exception("kiwicache.reload_exception")

    async def get_refill_lock(self):  # type: () -> bool
        """Lock loading from the expensive source.

        This lets us avoid all workers hitting database at the same time.

        :return: Whether we got the lock or not
        """
        try:
            return bool(
                await self.resources_redis.set(
                    self.redis_key + ':lock',
                    'locked',
                    expire=int(self.refill_lock_ttl.total_seconds()),
                    exist=self.resources_redis.SET_IF_NOT_EXIST,
                )
            )
        except aioredis.RedisError:
            pass

    async def refill_cache(self):
        """Cache the full data bundle in Redis."""
        if not await self.get_refill_lock():
            await asyncio.sleep(self.refill_lock_ttl.total_seconds())  # let the lock owner finish
            return

        try:
            source_data = await self.load_from_source()
            if not source_data:
                raise RuntimeError('load_from_source returned empty response!')

            self.call_attempt.reset()
            await self.save_to_cache(source_data)
            self.statsd and self.statsd.increment('kiwicache', tags=['name:' + self.name, 'status:success'])
        except Exception:
            self.logger.exception("kiwicache.source_exception")
            self.call_attempt.countdown()
            self.statsd and self.statsd.increment('kiwicache', tags=['name:' + self.name, 'status:load_error'])
