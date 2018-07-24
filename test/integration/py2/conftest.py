import attr
import pytest

from kw.cache import KiwiCache


@attr.s
class ArrayCache(KiwiCache):
    max_attempts = attr.ib(3, type=int, validator=attr.validators.instance_of(int))

    def load_from_source(self):
        return {"a": 101, "b": 102, "c": 103}

    def _get_refill_lock(self):
        return True


@pytest.fixture
def cache(redis, mocker):
    cache_instance = ArrayCache(redis)
    mocker.spy(cache_instance, "load_from_source")
    return cache_instance
