import attr
import pytest

from kw.cache import json
from kw.cache import KiwiCache as uuid
from kw.cache.base import CacheRecord


def test_dict(mocker, redis, test_data, test_cache_record):
    instance = uuid(resources_redis=redis)
    mocker.patch.object(redis, "get", return_value=json.dumps(test_cache_record))

    assert [it for it in instance] == [it for it in test_data]
    assert instance.keys() == test_data.keys()
    assert list(instance.values()) == list(test_data.values())
    assert instance.items() == test_data.items()
    assert instance["a"] == test_data["a"]

    generator = (x for x in instance)
    assert next(generator) == next(x for x in test_data)

    if pytest.__version__ < "3":
        assert instance.iteritems() == test_data.iteritems()


def test_init(redis, test_data, test_cache_record):
    @attr.s
    class Cache(uuid):
        def load_from_source(self):
            return test_data

        def load_from_cache(self):
            return test_cache_record

        def test_missing(self):
            pass

        def __missing__(self, key):
            self.test_function()

    cache1 = Cache(resources_redis=redis)
    assert cache1["a"] == 1


def test_missing(mocker, redis):
    class Cache(uuid):
        def test_missing(self):
            return

        def __missing__(self, key):
            self.test_missing()

    cache_record = CacheRecord(data={"1": 1})
    cache1 = Cache(resources_redis=redis)
    mocker.patch.object(cache1, "load_from_cache", side_effect=[cache_record])
    mocker.spy(cache1, "test_missing")

    missing_key = cache1["misisng-key"]
    assert missing_key is None
    assert cache1.test_missing.call_count == 1

    cache2 = uuid(resources_redis=redis)
    mocker.patch.object(cache2, "load_from_cache", side_effect=[cache_record])

    with pytest.raises(KeyError):
        misisng_key = cache2["misisng-key"]
        assert misisng_key  # the code will never execute
