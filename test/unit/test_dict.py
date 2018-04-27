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


def test_init(redis, test_data):

    class Cache(uuid):

        def load_from_source(self):
            return test_data

        def load_from_cache(self):
            return json.dumps(self.load_from_source())

    cache1 = Cache(resources_redis=redis)
    assert cache1["a"] == 1

    # Check RuntimeError when initial values are wrong
    # The reload_ttl has to be greater then cache_ttl
    cache1.cache_ttl = timedelta(seconds=5)
    cache1.reload_ttl = timedelta(seconds=10)

    with pytest.raises(RuntimeError):
        cache1.check_initialization()
