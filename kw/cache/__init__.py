import time
from datetime import timedelta, datetime

import redis
from future.moves.collections import UserDict
from .helpers import ReadOnlyDictMixin
from . import json


class KiwiCache(UserDict, ReadOnlyDictMixin):
    """Caches data from expensive sources to Redis and to memory."""

    instances = []  # type: List[KiwiCache]
    ttl = timedelta(minutes=1)
    refill_ttl = timedelta(seconds=5)
    resources_redis = None

    def __init__(self, resources_redis=None):  # type: (redis.Connection) -> None
        self.instances.append(self)

        if resources_redis is not None:
            self.resources_redis = resources_redis

        if self.resources_redis is None:
            raise RuntimeError('You must set a redis.Connection object')

        self.name = self.__class__.__name__
        self.expires_at = datetime.utcnow()
        self._data = {}  # type: dict

    @property
    def redis_key(self):
        return 'resource:' + self.name

    @property
    def data(self):
        self.maybe_reload()
        return self._data

    def load_from_source(self):  # type: () -> dict
        """Get the full data bundle from our expensive source."""
        raise NotImplementedError()

    def load_from_cache(self):  # type: () -> str
        """Get the full data bundle from cache."""
        return self.resources_redis.get(self.redis_key)

    def save_to_cache(self, data):  # type: (dict) -> None
        """Save the provided full data bundle to cache."""
        try:
            self.resources_redis.set(self.redis_key, json.dumps(data), ex=(self.ttl * 10))
        except redis.exceptions.ConnectionError:
            pass

    def reload(self):
        """Load the full data bundle, from cache, or if unavailable, from source."""
        try:
            cache_data = self.load_from_cache()
        except redis.exceptions.ConnectionError:
            return

        if cache_data:
            self._data = json.loads(cache_data)
            self.expires_at = datetime.utcnow() + self.ttl
        else:
            self.refill_cache()
            self.reload()

    def maybe_reload(self):  # type: () -> None
        """Load the full data bundle if it's too old."""
        if not self._data or self.expires_at < datetime.utcnow():
            try:
                self.reload()
            except:
                pass

    def get_refill_lock(self):  # type: () -> bool
        """Lock loading from the expensive source.

        This lets us avoid all workers hitting database at the same time.

        :return: Whether we got the lock or not
        """
        try:
            return bool(self.resources_redis.set(self.redis_key + ':lock', 'locked', ex=self.refill_ttl, nx=True))
        except redis.exceptions.ConnectionError:
            pass

    def refill_cache(self):
        """Cache the full data bundle in Redis."""
        if not self.get_refill_lock():
            time.sleep(self.refill_ttl.total_seconds())  # let the lock owner finish
            return

        try:
            source_data = self.load_from_source()
        except Exception:
            self.expire()
        else:
            if source_data:
                self.save_to_cache(source_data)
            else:
                self.expire()

    def expire(self):
        self.resources_redis.expire(self.redis_key, time=(self.ttl * 10))
