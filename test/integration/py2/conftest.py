from datetime import timedelta

import pytest

from kw.cache import KiwiCache


class ArrayCache(KiwiCache):
    refill_ttl = timedelta(seconds=1)

    def load_from_source(self):
        return {'a': 101, 'b': 102, 'c': 103}

    def get_refill_lock(self):
        return True


@pytest.fixture
def cache(redis, mocker):
    cache_instance = ArrayCache(redis)
    mocker.spy(cache_instance, 'load_from_source')
    return cache_instance
