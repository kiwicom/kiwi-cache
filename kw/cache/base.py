from datetime import datetime, timedelta
import sys
import time
from typing import Dict, Optional  # pylint: disable=unused-import

import attr
import redis
import structlog

from . import json, utils  # pylint: disable=unused-import
from .helpers import CallAttempt, ReadOnlyDictMixin

if sys.version_info >= (3, 0):
    from collections import UserDict
else:  # for Python 2
    from UserDict import IterableUserDict as UserDict  # pylint: disable=import-error

CACHE_RECORD_ATTRIBUTES = {"data", "timestamp"}


@attr.s
class CacheRecord(object):
    """Cache record with timestamp of creation and data."""

    data = attr.ib(None, type=dict)
    timestamp = attr.ib(None, type=float)

    def __attrs_post_init__(self):
        self.timestamp = self.timestamp if self.timestamp else utils.get_current_timestamp()


@attr.s
class BaseKiwiCache(object):
    """Helper class for load data from cache.

    Base instance attributes:
    - `resources_redis` - StrictRedis for communication with redis (cache) server
    - `cache_ttl` - timedelta for redis (cache) key expiration time
    - `refill_ttl` - timedelta for lock key expiration time
    - `metric` - str value of datadog metric

    Base class attributes:
    - `logger` - logger instance
    - `statsd` - datadog client instance
    - `json` - module for json related processing

    Method which can be typically overridden by subclasses:
    - `_key_suffix`
    """

    resources_redis = attr.ib(None, type=redis.StrictRedis, validator=attr.validators.instance_of(redis.StrictRedis))
    cache_ttl = attr.ib(
        None, type=timedelta, validator=attr.validators.optional(attr.validators.instance_of(timedelta))
    )
    refill_ttl = attr.ib(timedelta(seconds=5), type=timedelta, validator=attr.validators.instance_of(timedelta))
    metric = attr.ib("kiwicache", type=str, validator=attr.validators.instance_of(str))

    # class attributes
    logger = structlog.get_logger()
    statsd = None
    json = json

    def __attrs_post_init__(self):
        if self._cache_ttl is None:
            raise AttributeError("cache ttl missing")

    @property
    def name(self):
        """Name property."""
        return self.__class__.__name__

    @property
    def _cache_ttl(self):
        # type: () -> timedelta
        """Cache ttl."""
        return self.cache_ttl

    @property
    def _cache_key(self):
        # type: () -> str
        """Cache key string value.

        Inherited classes should not override this property, instead of that override _key_suffix property.
        """
        return "resource:{}".format(self.__key)

    @property
    def _refill_lock_key(self):
        # type: () -> str
        """Refill lock key string value.

        Inherited classes should not override this property, instead of that override _key_suffix property.
        """
        return "lock:{}".format(self.__key)

    @property
    def __key(self):
        # type: () -> str
        """Key string value.

        Inherited classes should not override this property, instead of that override _key_suffix property.
        """
        return self.name + (":{}".format(self._key_suffix) if self._key_suffix else "")

    @property
    def _key_suffix(self):
        # type: () -> Optional[str]
        """Suffix of _cache_key and _refill_lock_key.

        Inherited classes can override this property.
        """
        return None

    def load_from_cache(self):
        # type: () -> Optional[CacheRecord]
        """Load the full data bundle from cache."""
        try:
            value = self.resources_redis.get(self._cache_key)
        except redis.exceptions.ConnectionError:
            self._process_cache_error("kiwicache.load_failed")
            return None

        if value is None:
            return None

        cache_data = self.json.loads(value)
        if set(cache_data.keys()) != CACHE_RECORD_ATTRIBUTES:
            self._log_warning("kiwicache.malformed_cache_data")
            return None
        return CacheRecord(**cache_data)

    def save_to_cache(self, data):
        # type: (dict) -> None
        """Save the provided data bundle to cache."""
        cache_record = CacheRecord(data=data)
        try:
            self.resources_redis.set(self._cache_key, self.json.dumps(attr.asdict(cache_record)), ex=self._cache_ttl)
        except redis.exceptions.ConnectionError:
            self._process_cache_error("kiwicache.save_failed")
        else:
            self._increment_metric("success")

    def _get_refill_lock(self):
        # type: () -> Optional[bool]
        """Lock loading from the expensive source.

        This lets us avoid all workers hitting at the same time.
        :return: Whether we got the lock or not, None if connection to redis failed.
        """
        try:
            return bool(self.resources_redis.set(self._refill_lock_key, "locked", ex=self.refill_ttl, nx=True))
        except redis.exceptions.ConnectionError:
            self._process_cache_error("kiwicache.refill_lock_failed")
            return None

    def _wait_for_refill_lock(self):
        # type: () -> Optional[bool]
        """Wait for lock or reloaded data in cache (handles multiple workers).

        :return: Whether we got the lock or not, None if connection to redis failed.
        """
        start_timestamp = utils.get_current_timestamp()
        lock_check_period = 0.5
        while True:
            has_lock = self._get_refill_lock()
            if has_lock is None or has_lock is True:
                return has_lock

            self._log_warning("kiwicache.refill_locked")
            # let the lock owner finish
            lock_check_period = min(lock_check_period * 2, self.refill_ttl.total_seconds())
            time.sleep(lock_check_period)

            if self._is_refilled(start_timestamp):
                return False

    def _is_refilled(self, timestamp):
        # type: (float) -> bool
        """Return whether cache data was refilled from timestamp time.

        :param timestamp: timestamp of refill start
        :return: Whether cache data was refilled
        """
        cache_record = self.load_from_cache()
        return cache_record and cache_record.timestamp > timestamp

    def _release_refill_lock(self):
        # type: () -> Optional[bool]
        """Release loading lock from the source.

        This lets us avoid all workers hitting at the same time.
        :return: Whether we released the lock or not
        """
        try:
            return bool(self.resources_redis.delete(self._refill_lock_key))
        except redis.exceptions.ConnectionError:
            self._process_cache_error("kiwicache.release_lock_failed")
            return None

    def _prolong_cache_expiration(self):
        # type: () -> None
        """Prolong cache expiration."""
        try:
            self.resources_redis.expire(self._cache_key, time=self._cache_ttl)
        except redis.exceptions.ConnectionError:
            self._process_cache_error("kiwicache.prolong_expiration_failed")

    def _process_cache_error(self, msg):
        # type: (str) -> None
        """Process cache error.

        Inherited classes can override this method.
        :param msg: message
        """
        self._log_exception(msg)
        self._increment_metric("redis_error")

    def _log_warning(self, msg):
        # type: (str) -> None
        """Log warning.

        Inherited classes can override this method.
        :param msg: message
        """
        self.logger.warning(msg, resource=self.__key)

    def _log_exception(self, msg):
        # type: (str) -> None
        """Log warning.

        Inherited classes can override this method.
        :param msg: message
        """
        self.logger.exception(msg, resource=self.__key)

    def _log_error(self, msg):
        # type: (str) -> None
        """Log error.

        Inherited classes can override this method.
        :param msg: message
        """
        self.logger.error(msg, resource=self.__key)

    def _increment_metric(self, status):
        # type: (str) -> None
        """Increment datadog metric with defined status.

        Inherited classes should not override this method.
        :param status: metric status
        """
        if self.statsd:
            self.statsd.increment(self.metric, tags=["name:{}".format(self.name), "status:{}".format(status)])


@attr.s
class KiwiCache(BaseKiwiCache, UserDict, ReadOnlyDictMixin):
    """Caches data from expensive sources to Redis and to memory.

    Workflow for get data (item) is:
    1. If local `_data` is filled and not expired then return it
    2. If data exists in redis then return it
    3. Try refill redis data from source, in case of success return refilled data
    4. Save local `_data` to redis (if filled) and return it
    Also we can `refill` all data in redis using `instances` dict (current redis data are prolonged in case of failure).

    Base instance attributes:
    - `reload_ttl` - timedelta for local data expiration time
    - `expires_at` - local data expiration time = current time + `reload_ttl` in the time of data reload
    - `data` - local data dict
    - `max_attempts` - maximum attempts for refill cache (if negative - one attempt is used and no Exception is raised)
    - `_call_attempt` - local refill attempts countdown entity

    Base class attributes:
    - `instances` - dict of instances with one instance per each _cache_key

    Each subclass must implement `load_from_source` method.
    Method which can be typically overridden by subclasses:
    - `_process_refill_error`

    For another attributes and methods see parent classes docs.
    """

    reload_ttl = attr.ib(timedelta(minutes=1), type=timedelta, validator=attr.validators.instance_of(timedelta))
    expires_at = attr.ib(factory=datetime.utcnow, type=datetime, validator=attr.validators.instance_of(datetime))
    _data = attr.ib(attr.Factory(dict), type=dict, validator=attr.validators.instance_of(dict))
    max_attempts = attr.ib(-1, type=int, validator=attr.validators.instance_of(int))
    _call_attempt = attr.ib(init=False, type=CallAttempt)

    # class attributes
    instances = {}  # type: Dict[str, KiwiCache]

    def __attrs_post_init__(self):
        super(KiwiCache, self).__attrs_post_init__()
        self._add_instance()
        self._call_attempt = CallAttempt("{}.load_from_source".format(self.name.lower()), self.max_attempts)

    def _add_instance(self):
        """Add current instance to instances dict with _cache_key as dict key.

        Typically instances are used for cache refill so one instance per each _cache_key is saved.
        If you need all instances please override this method.
        """
        self.instances[self._cache_key] = self

    @reload_ttl.validator
    def reload_ttl_validator(self, attribute, value):
        if self._cache_ttl < value:
            raise AttributeError("The parameter cache_ttl has to be greater then reload_ttl.")

    @property
    def _cache_ttl(self):
        # type: () -> timedelta
        return self.cache_ttl if self.cache_ttl else self.reload_ttl * 10

    @property
    def data(self):
        self.maybe_reload()
        return self._data

    def load_from_source(self):
        # type: () -> dict
        """Get the full data bundle from our expensive source."""
        raise NotImplementedError()

    def reload(self):
        # type: () -> None
        """Load the full data bundle, from cache, or if unavailable, from source."""
        successful_reload = self.reload_from_cache()
        while not successful_reload:
            self.refill_cache()
            successful_reload = self.reload_from_cache()
            if self.max_attempts < 0 and not successful_reload:
                self._log_error("kiwicache.reload_failed")
                break

    def reload_from_cache(self):
        # type: () -> bool
        """Reload data from redis cache.

        :return: Whether the reload from cache succeeded or not.
        """
        cache_data = self.load_from_cache()

        if not cache_data:
            return False

        self._data = cache_data.data
        self.expires_at = datetime.utcnow() + self.reload_ttl
        return True

    def maybe_reload(self):
        # type: () -> None
        """Load the full data bundle if it's too old."""
        if not self._data or self.expires_at < datetime.utcnow():
            self.reload()

    def _prolong_cache_expiration(self):
        """Prolong cache expiration or refill if it expires and we have data locally."""
        super(KiwiCache, self)._prolong_cache_expiration()
        successful_reload = self.reload_from_cache()
        if not successful_reload and self._data:
            self.save_to_cache(self._data)

    def _process_refill_error(self, msg, exception=None):
        """Process refill error.

        Inherited classes can override this method.
        :param msg: message
        """
        self._prolong_cache_expiration()
        self._increment_metric("load_error")
        self._log_exception(msg)
        self._call_attempt.countdown()

    def refill_cache(self):
        # type: () -> None
        """Refill cache with the full data bundle from source in Redis."""
        if not self._wait_for_refill_lock():
            return

        try:
            source_data = self.load_from_source()
        except Exception as e:
            self._process_refill_error("kiwicache.source_exception", e)
            return

        if source_data:
            self.save_to_cache(source_data)
        else:
            self._process_refill_error("load_from_source returned empty response!")
