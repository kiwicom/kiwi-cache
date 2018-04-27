from datetime import timedelta
import sys

import pytest

from kw.cache.aio import AioKiwiCache as uut

pytestmark = pytest.mark.skipif(sys.version_info < (3, 5), reason='requires Python 3.5+')


@pytest.fixture(autouse=True)
def clean_instances_list():
    yield None
    uut.instances = []


@pytest.mark.asyncio
async def test_instances_list(get_aioredis):
    redis_client = await get_aioredis()
    instance_one = uut(redis_client)
    instance_two = uut(redis_client)
    assert uut.instances == [instance_one, instance_two]


@pytest.mark.asyncio
async def test_init(get_cache, mocker):
    cache = await get_cache()

    assert await cache.get('a') == 101
    assert cache.load_from_source.call_count == 1
    assert cache.load_from_cache.call_count == 2, (
        '1st call: Cache is empty, so try loading from source, which fails, '
        '2rd call: Cache is filled, so the call succeeds'
    )

    assert await cache.get('b') == 102
    assert cache.load_from_source.call_count == 1
    assert cache.load_from_cache.call_count == 2, (
        '1st call: Cache is empty, so try loading from source, which fails, '
        '2rd call: Cache is filled, so the call succeeds'
    )

    # Check RuntimeError when initial values are wrong
    # The reload_ttl has to be greater then cache_ttl
    cache.cache_ttl = timedelta(seconds=5)
    cache.reload_ttl = timedelta(seconds=10)

    with pytest.raises(RuntimeError):
        cache.check_initialization()


@pytest.mark.asyncio
async def test_error(get_cache, mocker):

    async def noop():
        return

    mocker.patch('asyncio.sleep', noop)

    cache = await get_cache()
    cache.load_from_source = mocker.Mock(side_effect=[
        Exception('Mock error'),
        cache.load_from_source(),
    ])

    assert await cache.get('a') == 101
    assert cache.load_from_source.call_count == 2, 'Load should be called a second time after first call fails'
    assert cache.load_from_cache.call_count == 3, (
        '1st call: Cache is empty, so try loading from source, which fails, '
        '2nd call: Cache is empty, so try loading from source, which succeeds and fills cache, '
        '3rd call: Cache is filled, so the call succeeds'
    )


@pytest.mark.asyncio
async def test_ttl(get_cache, mocker):
    cache = await get_cache()
    cache.load_from_source = mocker.Mock(side_effect=[cache.load_from_source(), ])

    cache.cache_ttl = timedelta(hours=1)
    await cache.reload()
    ttl = await cache.resources_redis.ttl(cache.redis_key)
    assert ttl == timedelta(hours=1).total_seconds()

    cache.cache_ttl = timedelta(minutes=1)
    await cache.reload()
    await cache.acheck_initialization()
    ttl = await cache.resources_redis.ttl(cache.redis_key)
    assert ttl == timedelta(minutes=1).total_seconds()


@pytest.mark.asyncio
async def test_maybe_reload(get_cache, mocker, frozen_time):
    cache = await get_cache()

    await cache.maybe_reload()
    assert cache.load_from_source.call_count == 1
    assert cache.load_from_cache.call_count == 2, (
        '1st call: Cache is empty, so try loading from source, which fails, '
        '2rd call: Cache is filled, so the call succeeds'
    )

    cache._data = {1: 2}
    frozen_time.tick(timedelta(days=1))
    await cache.maybe_reload()
    assert cache.load_from_source.call_count == 1, 'Since Redis key did not expire, no need to reload from source'
    assert cache.load_from_cache.call_count == 3

    await cache.maybe_reload()
    assert cache.load_from_source.call_count == 1, 'Since Redis key did not expire, no need to reload from source'
    assert cache.load_from_cache.call_count == 3
