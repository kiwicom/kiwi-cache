from datetime import datetime, timedelta

import pytest

from .conftest import ArrayCache


def test_load_from_source(cache):
    assert cache["a"] == 101
    assert cache.load_from_source.call_count == 1

    assert cache["b"] == 102
    assert cache.load_from_source.call_count == 1

    assert sorted([x for x in cache])[2] == "c"
    assert cache.load_from_source.call_count == 1


@pytest.mark.usefixtures("frozen_time")
def test_error(cache, mocker):
    mocker.patch("time.sleep")
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
