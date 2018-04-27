import pytest


@pytest.fixture
def redis(mocker):
    test_redis = mocker.Mock()
    mocker.patch.object(test_redis, "ttl", return_value=1)
    return test_redis


@pytest.fixture
def test_data():
    return {"a": 1, "b": 2, "c": "hello"}
