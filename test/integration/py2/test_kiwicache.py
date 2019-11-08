from datetime import datetime, timedelta

import pytest
from redis import exceptions

from kw.cache.helpers import CallAttemptException

from .conftest import ArrayCache


def test_load_from_source(cache):
    assert cache["a"] == 101
    assert cache.load_from_source.call_count == 1

    assert cache["b"] == 102
    assert cache.load_from_source.call_count == 1

    assert sorted(cache)[2] == "c"
    assert cache.load_from_source.call_count == 1


def test_allow_empty(cache, mocker):
    cache.allow_empty_data = True
    mocker.patch.object(cache, "load_from_source", return_value={})

    assert cache.get("a") is None
    with pytest.raises(KeyError):
        assert not cache["b"]
    assert cache.load_from_source.call_count == 1


@pytest.mark.usefixtures("frozen_time")
def test_error(cache, mocker):
    mocker.patch.object(cache, "load_from_source", side_effect=[Exception("Mock error"), cache.load_from_source()])

    assert cache["a"] == 101
    assert cache.load_from_source.call_count == 2, "Load should be called a second time after first call fails"


def test_init_ttl(cache, mocker):
    mocker.patch.object(cache, "load_from_source", side_effect=[cache.load_from_source()])

    cache.cache_ttl = timedelta(hours=1)
    cache.refill_cache()
    ttl = cache.resources_redis.ttl(cache._cache_key)
    assert ttl == timedelta(hours=1).total_seconds()

    cache.cache_ttl = timedelta(minutes=1)
    cache.refill_cache()
    ttl = cache.resources_redis.ttl(cache._cache_key)
    assert ttl == timedelta(minutes=1).total_seconds()


@pytest.mark.parametrize(
    "valid_params",
    [
        {"cache_ttl": timedelta(minutes=1)},
        {"refill_ttl": timedelta(seconds=30)},
        {"reload_ttl": timedelta(minutes=5)},
        {"expires_at": datetime.utcnow() + timedelta(hours=1)},
        {"max_attempts": 10},
    ],
)
def test_init(redis, valid_params):
    params = {"resources_redis": redis}
    params.update(valid_params)
    reasource = ArrayCache(**params)
    for param, value in params.items():
        assert getattr(reasource, param) == value


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
def test_validators(redis, invalid_params, error):
    params = {"resources_redis": redis}
    params.update(invalid_params)
    with pytest.raises(error):
        ArrayCache(**params)


@pytest.mark.parametrize("max_attempts", [-1, 3])
@pytest.mark.usefixtures("frozen_time")
def test_redis_error(redis, mocker, max_attempts):
    cache = ArrayCache(redis, max_attempts=max_attempts)
    cache._data = {"a": 213}
    cache.expires_at = datetime.utcnow()

    mocker.spy(cache, "load_from_source")
    mocker.spy(cache, "load_from_cache")
    mocker.patch.object(cache.resources_redis, "set", side_effect=exceptions.RedisError)
    mocker.patch.object(cache.resources_redis, "get", side_effect=exceptions.RedisError)

    if max_attempts < 0:
        assert cache["a"] == 213
    else:
        with pytest.raises(CallAttemptException):
            cache.get("a")

    assert cache.load_from_source.call_count == 0
    assert cache.load_from_cache.call_count == (2 if max_attempts < 3 else max_attempts)
    assert cache.expires_at == datetime.utcnow() + cache.reload_ttl
