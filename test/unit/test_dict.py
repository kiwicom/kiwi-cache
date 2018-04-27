import json

import pytest

from kw.cache import KiwiCache as uuid


def test_dict(redis, test_data, mocker):
    instance_one = uuid(resources_redis=redis)
    mocker.patch.object(redis, "get", return_value=json.dumps(test_data))

    assert [it for it in instance_one] == [it for it in test_data]
    assert instance_one.keys() == (test_data.keys())
    assert list(instance_one.values()) == list(test_data.values())
    assert instance_one.items() == test_data.items()
    assert instance_one["a"] == test_data["a"]

    generator = (x for x in instance_one)
    assert next(generator) == next(x for x in test_data)

    if pytest.__version__ < "3":
        assert instance_one.iteritems() == test_data.iteritems()


def test_init(redis, test_data):

    class Cache(uuid):

        def load_from_source(self):
            return test_data

        def load_from_cache(self):
            return json.dumps(self.load_from_source())

    cache1 = Cache(resources_redis=redis)

    assert cache1["a"] == 1
