import aioredis
import pytest

from kw.cache.aio import AioKiwiCache


@pytest.fixture
def get_aioredis(redis_url, event_loop):

    async def coroutine():
        client = await aioredis.create_redis(redis_url, loop=event_loop)
        await client.flushall()
        return client

    return coroutine


class ArrayCache(AioKiwiCache):

    async def load_from_source(self):
        return {'a': 101, 'b': 102, 'c': 103}

    async def get_refill_lock(self):
        return True


@pytest.fixture
def get_cache(get_aioredis, mocker):  # pylint: disable=redefined-outer-name

    async def coroutine():
        cache_instance = ArrayCache(await get_aioredis())
        mocker.spy(cache_instance, 'load_from_cache')
        mocker.spy(cache_instance, 'load_from_source')
        return cache_instance

    return coroutine
