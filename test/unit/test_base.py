from kw.cache import json, utils


def test_resource(cache):
    assert cache._cache_key == "resource:UUTResource"


def test_load_from_cache(cache, redis, test_cache_record):
    redis.get.return_value = json.dumps(test_cache_record)
    assert cache.load_from_cache() == test_cache_record
    redis.get.assert_called_once_with(cache._cache_key)


def test_save_to_cache(mocker, cache, redis, test_data, test_cache_record):
    mocker.patch.object(utils, "get_current_timestamp", return_value=test_cache_record.timestamp)
    cache.save_to_cache(test_data)
    redis.set.assert_called_once_with(cache._cache_key, json.dumps(test_cache_record), ex=cache._cache_ttl)


def test_refill_cache_no_redis(mocker, cache, redis):
    load_from_source = mocker.patch.object(cache, "load_from_source")
    mocker.patch.object(cache, "_get_refill_lock", return_value=None)
    save_to_cache = mocker.patch.object(cache, "save_to_cache")
    reload_from_cache = mocker.patch.object(cache, "reload_from_cache")

    cache.refill_cache()
    save_to_cache.assert_not_called()
    load_from_source.assert_not_called()
    reload_from_cache.assert_not_called()
    redis.expire.assert_not_called()


def test_refill_cache_source_with_error(mocker, cache, redis):
    mocker.patch.object(cache, "load_from_source", side_effect=Exception())
    mocker.patch.object(cache, "_get_refill_lock", return_value=True)
    save_to_cache = mocker.patch.object(cache, "save_to_cache")
    reload_from_cache = mocker.patch.object(cache, "reload_from_cache")
    refill_fail = mocker.spy(cache, "_process_refill_error")

    cache.refill_cache()
    save_to_cache.assert_not_called()
    assert reload_from_cache.call_count == 1
    redis.expire.assert_called_once_with(cache._cache_key, time=cache._cache_ttl)
    assert refill_fail.call_count == 1


def test_refill_cache_no_source(mocker, cache, redis):
    mocker.patch.object(cache, "_get_refill_lock", return_value=True)
    save_to_cache = mocker.patch.object(cache, "save_to_cache")
    reload_from_cache = mocker.patch.object(cache, "reload_from_cache")

    cache.refill_cache()
    save_to_cache.assert_not_called()
    assert reload_from_cache.call_count == 1
    redis.expire.assert_called_once_with(cache._cache_key, time=cache._cache_ttl)


def test_refill_cache_no_source_with_wait(mocker, cache, redis):
    mocker.patch("time.sleep")
    mocker.patch.object(cache, "_get_refill_lock", side_effect=[False, False, True])
    save_to_cache = mocker.patch.object(cache, "save_to_cache")
    reload_from_cache = mocker.patch.object(cache, "reload_from_cache", return_value=False)
    is_refilled = mocker.patch.object(cache, "_is_refilled", return_value=False)

    cache.refill_cache()
    save_to_cache.assert_not_called()
    assert reload_from_cache.call_count == 1
    assert is_refilled.call_count == 2
    redis.expire.assert_called_once_with(cache._cache_key, time=cache._cache_ttl)


def test_refill_cache_source(mocker, cache, redis, test_data):
    mocker.patch.object(cache, "load_from_source", return_value=test_data)
    mocker.patch.object(cache, "_get_refill_lock", return_value=True)
    save_to_cache = mocker.patch.object(cache, "save_to_cache")
    reload_from_cache = mocker.patch.object(cache, "reload_from_cache")

    cache.refill_cache()
    save_to_cache.assert_called_with(test_data)
    reload_from_cache.assert_not_called()
    redis.expire.assert_not_called()


def test_refill_cache_source_with_wait(mocker, cache, redis, test_data):
    mocker.patch("time.sleep")
    mocker.patch.object(cache, "load_from_source", return_value=test_data)
    mocker.patch.object(cache, "_get_refill_lock", side_effect=[False, False, True])
    save_to_cache = mocker.patch.object(cache, "save_to_cache")
    reload_from_cache = mocker.patch.object(cache, "reload_from_cache", return_value=False)
    is_refilled = mocker.patch.object(cache, "_is_refilled", return_value=False)

    cache.refill_cache()
    save_to_cache.assert_called_with(test_data)
    reload_from_cache.assert_not_called()
    assert is_refilled.call_count == 2
    redis.expire.assert_not_called()


def test_reload_from_cache_with_data(mocker, cache, test_data, test_cache_record):
    mocker.patch.object(cache, "load_from_cache", return_value=test_cache_record)

    assert cache.reload_from_cache()
    assert set(test_data.keys()) == set(cache.keys())
    for key in test_data.keys():
        assert cache[key] == test_data[key]


def test_reload_from_cache_no_data(mocker, cache):
    _data = mocker.patch.object(cache, "_data", new_callable=mocker.PropertyMock)
    expires_at = mocker.patch.object(cache, "expires_at", new_callable=mocker.PropertyMock)

    assert cache.reload_from_cache() is False
    _data.assert_not_called()
    expires_at.assert_not_called()
