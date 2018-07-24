import attr
from freezegun import freeze_time
import pytest

from kw.cache import KiwiCache
from kw.cache.base import CacheRecord


@pytest.fixture(autouse=True)
def disable_validators():
    attr.set_run_validators(False)


@pytest.fixture
def redis(mocker):
    test_redis = mocker.Mock()
    mocker.patch.object(test_redis, "ttl", return_value=1)
    mocker.patch.object(test_redis, "get", return_value=None)
    return test_redis


@pytest.fixture
def test_data():
    return {"a": 1, "b": 2, "c": "hello"}


@pytest.fixture
def test_cache_record(test_data):  # pylint: disable=redefined-outer-name
    return CacheRecord(timestamp=1234, data=test_data)


@attr.s
class UUTResource(KiwiCache):
    def load_from_source(self):
        return None


@pytest.fixture
def cache(redis):  # pylint: disable=redefined-outer-name
    return UUTResource(resources_redis=redis)


@pytest.fixture
def frozen_time():
    ft = freeze_time("2000-01-01 00:00:00")
    yield ft.start()
    ft.stop()
