import asyncio
from datetime import timedelta, datetime

import aioredis

from . import json


class AioKiwiCache:
    """Caches data from expensive sources to Redis and to memory."""

    instances = []  # type: List[AioKiwiCache]
    ttl = timedelta(minutes=1)
    refill_ttl = timedelta(seconds=5)
    resources_redis = None

    def __init__(self, resources_redis=None):  # type: (aioredis.Redis) -> None
        self.instances.append(self)

        if resources_redis is not None:
            self.resources_redis = resources_redis

        if self.resources_redis is None:
            raise RuntimeError('You must set an aioredis.Redis object')

        self.name = self.__class__.__name__
        self.expires_at = datetime.utcnow()
        self._data = {}  # type: dict

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
            await self.resources_redis.set(self.redis_key, json.dumps(data), expire=int(self.ttl.total_seconds() * 10))
        except aioredis.RedisError:
            pass

    async def reload(self):
        """Load the full data bundle, from cache, or if unavailable, from source."""
        try:
            cache_data = await self.load_from_cache()
        except aioredis.RedisError:
            return

        if cache_data:
            self._data = json.loads(cache_data)
            self.expires_at = datetime.utcnow() + self.ttl
        else:
            await self.refill_cache()
            await self.reload()

    async def maybe_reload(self):  # type: () -> None
        """Load the full data bundle if it's too old."""
        if not self._data or self.expires_at < datetime.utcnow():
            try:
                await self.reload()
            except:
                pass

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
                    expire=int(self.refill_ttl.total_seconds()),
                    exist=self.resources_redis.SET_IF_NOT_EXIST,
                )
            )
        except aioredis.RedisError:
            pass

    async def refill_cache(self):
        """Cache the full data bundle in Redis."""
        if not await self.get_refill_lock():
            await asyncio.sleep(self.refill_ttl.total_seconds())  # let the lock owner finish
            return

        try:
            source_data = await self.load_from_source()
        except Exception:
            await self.expire()
        else:
            if source_data:
                await self.save_to_cache(source_data)
            else:
                await self.expire()

    async def expire(self):
        await self.resources_redis.expire(self.redis_key, timeout=int(self.ttl.total_seconds()) * 10)
