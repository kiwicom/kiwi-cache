import time
from datetime import timedelta, datetime

import sys
import logging
import redis
if sys.version_info >= (3, 0):
    from collections import UserDict
else:  # for Python 2
    from UserDict import IterableUserDict as UserDict  # pylint: disable=import-error

from .helpers import ReadOnlyDictMixin, CallAttempt, CallAttemptException
from . import json


class KiwiCache(UserDict, ReadOnlyDictMixin):
    """Caches data from expensive sources to Redis and to memory."""

    instances = []  # type: List[KiwiCache]
    reload_ttl = timedelta(minutes=1)
    cache_ttl = reload_ttl * 10
    refill_lock_ttl = timedelta(seconds=5)
    resources_redis = None

    def __init__(self, resources_redis=None, logger=None, statsd=None):
        # type: (redis.Connection, logging.Logger, datadog.DogStatsd) -> None

        self.instances.append(self)

        if resources_redis is not None:
            self.resources_redis = resources_redis

        self.name = self.__class__.__name__
        self.expires_at = datetime.utcnow()
        self._data = {}  # type: dict
        self.logger = logger if logger else logging.getLogger(__name__)
        self.statsd = statsd
        self.call_attempt = CallAttempt("{}.load_from_source".format(self.name.lower()))

        self.check_initialization()

    @property
    def redis_key(self):
        return 'resource:' + self.name

    @property
    def data(self):
        self.maybe_reload()
        return self._data

    def check_initialization(self):
        if self.resources_redis is None:
            raise RuntimeError('You must set a redis.Connection object')

        if self.cache_ttl < self.reload_ttl:
            raise RuntimeError('The parameter cache_ttl has to be greater then reload_ttl.')

        if self.resources_redis.ttl(self.redis_key) > int(self.reload_ttl.total_seconds()):
            self.resources_redis.expire(self.redis_key, int(self.reload_ttl.total_seconds()))

    def load_from_source(self):  # type: () -> dict
        """Get the full data bundle from our expensive source."""
        raise NotImplementedError()

    def load_from_cache(self):  # type: () -> str
        """Get the full data bundle from cache."""
        return self.resources_redis.get(self.redis_key)

    def save_to_cache(self, data):  # type: (dict) -> None
        """Save the provided full data bundle to cache."""
        try:
            self.resources_redis.set(self.redis_key, json.dumps(data), ex=self.cache_ttl)
        except redis.exceptions.ConnectionError:
            self.logger.exception("kiwicache.save_failed")
            self.statsd and self.statsd.increment('kiwicache', tags=['name:' + self.name, 'status:redis_error'])

    def reload(self):
        """Load the full data bundle, from cache, or if unavailable, from source."""
        try:
            cache_data = self.load_from_cache()
        except redis.exceptions.ConnectionError:
            self.logger.exception("kiwicache.load_failed")
            self.statsd and self.statsd.increment('kiwicache', tags=['name:' + self.name, 'status:redis_error'])
            return

        if cache_data:
            self._data = json.loads(cache_data)
            self.expires_at = datetime.utcnow() + self.reload_ttl
            self.statsd and self.statsd.increment('kiwicache', tags=['name:' + self.name, 'status:success'])
        else:
            self.refill_cache()
            self.reload()

    def maybe_reload(self):  # type: () -> None
        """Load the full data bundle if it's too old."""
        if not self._data or self.expires_at < datetime.utcnow():
            try:
                self.reload()
            except CallAttemptException:
                raise
            except Exception:
                self.logger.exception("kiwicache.reload_exception")

    def get_refill_lock(self):  # type: () -> bool
        """Lock loading from the expensive source.

        This lets us avoid all workers hitting database at the same time.

        :return: Whether we got the lock or not
        """
        try:
            return bool(self.resources_redis.set(self.redis_key + ':lock', 'locked', ex=self.refill_lock_ttl, nx=True))
        except redis.exceptions.ConnectionError:
            self.logger.exception("kiwicache.redis_exception")

    def refill_cache(self):
        """Cache the full data bundle in Redis."""
        if not self.get_refill_lock():
            time.sleep(self.refill_lock_ttl.total_seconds())  # let the lock owner finish
            return

        try:
            source_data = self.load_from_source()
            if not source_data:
                raise RuntimeError('load_from_source returned empty response!')

            self.call_attempt.reset()
            self.save_to_cache(source_data)
            self.statsd and self.statsd.increment('kiwicache', tags=['name:' + self.name, 'status:success'])
        except Exception:
            self.logger.exception("kiwicache.source_exception")
            self.call_attempt.countdown()
            self.statsd and self.statsd.increment('kiwicache', tags=['name:' + self.name, 'status:load_error'])
