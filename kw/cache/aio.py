import asyncio
from datetime import datetime
from typing import Any, Dict, ItemsView, KeysView, Optional, ValuesView

import aioredis
import attr

from . import utils
from .base import BaseKiwiCache, CACHE_RECORD_ATTRIBUTES, CacheRecord, KiwiCache
from .helpers import CallAttempt, CallAttemptException


@attr.s
class AioBaseKiwiCache(BaseKiwiCache):
    """Helper class for load data from cache using asyncio and aioredis."""

    resources_redis = attr.ib(None, type=aioredis.Redis, validator=attr.validators.instance_of(aioredis.Redis))

    async def load_from_cache(self) -> Optional[CacheRecord]:
        try:
            value = await self.resources_redis.get(self._cache_key)
        except aioredis.RedisError:
            self._process_cache_error("kiwicache.load_failed")
            return None

        if value is None:
            return None

        cache_data = self.json.loads(value)
        if set(cache_data.keys()) != CACHE_RECORD_ATTRIBUTES:
            self._log_warning("kiwicache.malformed_cache_data")
            return None
        return CacheRecord(**cache_data)

    async def save_to_cache(self, data: dict) -> None:
        cache_record = CacheRecord(data=data)
        try:
            await self.resources_redis.set(
                self._cache_key, self.json.dumps(attr.asdict(cache_record)), expire=int(self._cache_ttl.total_seconds())
            )
        except aioredis.RedisError:
            self._process_cache_error("kiwicache.save_failed")
        else:
            self._increment_metric("success")

    async def _get_refill_lock(self) -> Optional[bool]:
        try:
            return bool(
                await self.resources_redis.set(
                    self._refill_lock_key,
                    "locked",
                    expire=int(self.refill_ttl.total_seconds()),
                    exist=self.resources_redis.SET_IF_NOT_EXIST,
                )
            )
        except aioredis.RedisError:
            self._process_cache_error("kiwicache.refill_lock_failed")
            return None

    async def _wait_for_refill_lock(self) -> Optional[bool]:
        start_timestamp = utils.get_current_timestamp()
        lock_check_period = 0.5
        while True:
            has_lock = await self._get_refill_lock()
            if has_lock is None or has_lock is True:
                return has_lock

            self._log_warning("kiwicache.refill_locked")
            # let the lock owner finish
            lock_check_period = min(lock_check_period * 2, self.refill_ttl.total_seconds())
            await asyncio.sleep(lock_check_period)

            if await self._is_refilled(start_timestamp):
                return False

    async def _is_refilled(self, timestamp: float) -> bool:
        cache_record = await self.load_from_cache()
        return cache_record and cache_record.timestamp > timestamp

    async def _release_refill_lock(self) -> Optional[bool]:
        try:
            return bool(await self.resources_redis.delete(self._refill_lock_key))
        except aioredis.RedisError:
            self._process_cache_error("kiwicache.release_lock_failed")
            return None

    async def _prolong_cache_expiration(self) -> None:
        try:
            await self.resources_redis.expire(self._cache_key, timeout=int(self._cache_ttl.total_seconds()))
        except aioredis.RedisError:
            self._process_cache_error("kiwicache.prolong_expiration_failed")


@attr.s
class AioKiwiCache(AioBaseKiwiCache, KiwiCache):
    """Caches data from expensive sources to Redis and to memory using asyncio."""

    instances: Dict[str, "AioKiwiCache"] = {}

    def __attrs_post_init__(self) -> None:
        super().__attrs_post_init__()
        self._add_instance()
        self._call_attempt = CallAttempt("{}.load_from_source".format(self.name.lower()), self.max_attempts)

    async def getitem(self, key: Any) -> Any:
        data = await self.get_data()
        if key not in data:
            return self.__missing__(key)
        return data[key]

    def __missing__(self, key: Any) -> None:
        raise KeyError

    async def get(self, key: Any, default: Any = None) -> None:
        return (await self.get_data()).get(key, default)

    async def contains(self, key: Any) -> bool:
        return key in await self.get_data()

    async def keys(self) -> KeysView:
        return (await self.get_data()).keys()

    async def values(self) -> ValuesView:
        return (await self.get_data()).values()

    async def items(self) -> ItemsView:
        return (await self.get_data()).items()

    async def get_data(self) -> dict:
        await self.maybe_reload()
        return self._data

    async def reload(self) -> None:
        successful_reload = await self.reload_from_cache()
        while not successful_reload:
            try:
                await self.refill_cache()
            except CallAttemptException:
                self._prolong_data_expiration()
                raise

            successful_reload = await self.reload_from_cache()
            if self.max_attempts < 0 and not successful_reload:
                self._prolong_data_expiration()
                self._log_error("kiwicache.reload_failed")
                break

    async def reload_from_cache(self) -> bool:
        cache_data = await self.load_from_cache()

        if not cache_data:
            return False

        self._data = cache_data.data
        self._prolong_data_expiration()
        return True

    async def maybe_reload(self) -> None:
        if self.expires_at <= datetime.utcnow() or (not self._data and not self.allow_empty_data):
            await self.reload()

    async def _prolong_cache_expiration(self) -> None:
        await super()._prolong_cache_expiration()
        successful_reload = await self.reload_from_cache()
        if not successful_reload and self._data:
            await self.save_to_cache(self._data)

    async def _process_refill_error(self, msg: str, exception: Exception = None) -> None:
        await self._prolong_cache_expiration()
        self._increment_metric("load_error")
        self._log_exception(msg)
        self._call_attempt.countdown()

    async def refill_cache(self) -> None:
        has_lock = await self._wait_for_refill_lock()
        if not has_lock:
            if has_lock is None:
                # redis error
                self._call_attempt.countdown()
            return

        try:
            try:
                source_data = await self.load_from_source()
            except Exception as e:
                await self._process_refill_error("kiwicache.source_exception", e)
                return

            if source_data or self.allow_empty_data:
                await self.save_to_cache(source_data)
            else:
                await self._process_refill_error("load_from_source returned empty response!")
        finally:
            await self._release_refill_lock()

    async def load_from_source(self) -> dict:
        raise NotImplementedError()
