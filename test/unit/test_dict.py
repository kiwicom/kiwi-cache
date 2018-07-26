import json
from datetime import timedelta

import pytest

from kw.cache import KiwiCache as uuid


def test_dict(redis, test_data, mocker):
    instance = uuid(resources_redis=redis)
    mocker.patch.object(redis, "get", return_value=json.dumps(test_data))

    assert [it for it in instance] == [it for it in test_data]
    assert instance.keys() == test_data.keys()
    assert list(instance.values()) == list(test_data.values())
    assert instance.items() == test_data.items()
    assert instance["a"] == test_data["a"]

    generator = (x for x in instance)
    assert next(generator) == next(x for x in test_data)

    if pytest.__version__ < "3":
        assert instance.iteritems() == test_data.iteritems()


def test_init(redis, test_data, mocker):
    class Cache(uuid):
        def load_from_source(self):
            return test_data

        def load_from_cache(self):
            return json.dumps(self.load_from_source())

        def test_missing(self):
            pass

        def __missing__(self, key):
            self.test_function()

    cache1 = Cache(resources_redis=redis)
    assert cache1["a"] == 1

    # Check RuntimeError when initial values are wrong
    # The reload_ttl has to be greater then cache_ttl
    cache1.cache_ttl = timedelta(seconds=5)
    cache1.reload_ttl = timedelta(seconds=10)

    with pytest.raises(RuntimeError):
        cache1.check_initialization()


def test_missing(redis, mocker):
    class Cache(uuid):
        def test_missing(self):
            return

        def __missing__(self, key):
            self.test_missing()

    cache1 = Cache(resources_redis=redis)
    mocker.patch.object(cache1, "load_from_cache", side_effect=[b'{"1": 1}'])
    mocker.spy(cache1, "test_missing")

    misisng_key = cache1["misisng-key"]
    assert misisng_key is None
    assert cache1.test_missing.call_count == 1

    cache2 = uuid(resources_redis=redis)
    mocker.patch.object(cache2, "load_from_cache", side_effect=[b'{"1": 1}'])

    with pytest.raises(KeyError):
        misisng_key = cache2["misisng-key"]
        assert misisng_key  # the code will never execute
