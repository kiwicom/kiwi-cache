from datetime import datetime, timedelta
import sys

import aioredis
import pytest

from kw.cache.aio import AioKiwiCache as uut
from kw.cache.helpers import CallAttemptException

pytestmark = pytest.mark.skipif(sys.version_info < (3, 5), reason="requires Python 3.5+")


@pytest.fixture(autouse=True)
def clean_instances_list():
    yield None
    uut.instances = {}


@pytest.mark.asyncio
async def test_instances_list(get_aioredis, get_cache):
    redis_client = await get_aioredis()
    instance_one = uut(resources_redis=redis_client)
    await get_cache()
    instance_three = await get_cache()
    assert uut.instances == {"resource:AioKiwiCache": instance_one, "resource:ArrayCache": instance_three}


@pytest.mark.asyncio
async def test_init(get_cache):
    cache = await get_cache()

    assert await cache.get("a") == 101
    assert cache.load_from_source.call_count == 1
    assert cache.load_from_cache.call_count == 2, (
        "1st call: Cache is empty, so try loading from source, which fails, "
        "2rd call: Cache is filled, so the call succeeds"
    )

    assert await cache.get("b") == 102
    assert cache.load_from_source.call_count == 1
    assert cache.load_from_cache.call_count == 2, (
        "1st call: Cache is empty, so try loading from source, which fails, "
        "2rd call: Cache is filled, so the call succeeds"
    )


@pytest.mark.parametrize(
    ("invalid_params", "error"),
    [
        ({"resources_redis": None}, TypeError),
        ({"resources_redis": "redis"}, TypeError),
        ({"cache_ttl": 5}, TypeError),
        ({"refill_ttl": None}, TypeError),
        ({"refill_ttl": 10}, TypeError),
        ({"metric": None}, TypeError),
        ({"metric": 1}, TypeError),
        ({"reload_ttl": None}, TypeError),
        ({"reload_ttl": 5}, TypeError),
        ({"expires_at": None}, TypeError),
        ({"expires_at": timedelta(seconds=5)}, TypeError),
        ({"max_attempts": None}, TypeError),
        ({"max_attempts": "3"}, TypeError),
        ({"cache_ttl": timedelta(seconds=5), "reload_ttl": timedelta(seconds=10)}, AttributeError),
    ],
)
@pytest.mark.asyncio
async def test_validators(get_aioredis, invalid_params, error):
    params = {"resources_redis": await get_aioredis()}
    params.update(invalid_params)
    with pytest.raises(error):
        uut(**params)


@pytest.mark.asyncio
async def test_allow_empty(get_cache, mocker):
    cache = await get_cache(allow_empty_data=True)

    async def empty_load():
        return {}

    mocker.patch.object(cache, "load_from_source", empty_load)
    mocker.spy(cache, "load_from_source")

    assert await cache.get("a") is None
    with pytest.raises(KeyError):
        assert not await cache.getitem("b")
    assert cache.load_from_source.call_count == 1


@pytest.mark.asyncio
async def test_error(get_cache, mocker):
    cache = await get_cache(max_attempts=2)
    cache.load_from_source = mocker.Mock(side_effect=[Exception("Mock error"), cache.load_from_source()])

    assert await cache.get("a") == 101
    assert cache.load_from_source.call_count == 2, "Load should be called a second time after first call fails"
    assert cache.load_from_cache.call_count == 4, (
        "1st call: Cache is empty, so try loading from source, which fails, "
        "2nd call: Prolong cache expiration after loading fail, "
        "3rd call: Cache is empty, so try loading from source, which succeeds and fills cache, "
        "4th call: Cache is filled, so the call succeeds"
    )


@pytest.mark.asyncio
async def test_ttl(get_cache):
    cache = await get_cache(cache_ttl=timedelta(hours=1))
    await cache.reload()
    ttl = await cache.resources_redis.ttl(cache._cache_key)
    assert ttl == timedelta(hours=1).total_seconds()

    cache.cache_ttl = timedelta(minutes=1)
    await cache.refill_cache()
    ttl = await cache.resources_redis.ttl(cache._cache_key)
    assert ttl == timedelta(minutes=1).total_seconds()


@pytest.mark.asyncio
async def test_maybe_reload(get_cache, frozen_time):
    cache = await get_cache()

    await cache.maybe_reload()
    assert cache.load_from_source.call_count == 1
    assert cache.load_from_cache.call_count == 2, (
        "1st call: Cache is empty, so try loading from source, which fails, "
        "2rd call: Cache is filled, so the call succeeds"
    )

    cache._data = {1: 2}
    frozen_time.tick(timedelta(days=1))
    await cache.maybe_reload()
    assert cache.load_from_source.call_count == 1, "Since Redis key did not expire, no need to reload from source"
    assert cache.load_from_cache.call_count == 3

    await cache.maybe_reload()
    assert cache.load_from_source.call_count == 1, "Since Redis key did not expire, no need to reload from source"
    assert cache.load_from_cache.call_count == 3


@pytest.mark.asyncio
async def test_missing(get_cache, mocker):
    cache = await get_cache()
    with pytest.raises(KeyError):
        await cache.getitem("missing-key")

    missing = mocker.patch.object(cache, "__missing__")
    await cache.getitem("missing-key")
    assert missing.call_count == 1


@pytest.mark.parametrize("max_attempts", [-1, 3])
@pytest.mark.usefixtures("frozen_time")
@pytest.mark.asyncio
async def test_redis_error(get_cache, mocker, max_attempts):
    cache = await get_cache(max_attempts=max_attempts)
    cache._data = {"a": 213}
    cache.expires_at = datetime.utcnow()

    mocker.patch.object(cache.resources_redis, "set", side_effect=aioredis.RedisError)
    mocker.patch.object(cache.resources_redis, "get", side_effect=aioredis.RedisError)

    if max_attempts < 0:
        assert await cache.get("a") == 213
    else:
        with pytest.raises(CallAttemptException):
            await cache.get("a")

    assert cache.load_from_source.call_count == 0
    assert cache.load_from_cache.call_count == (2 if max_attempts < 3 else max_attempts)
    assert cache.expires_at == datetime.utcnow() + cache.reload_ttl
