import pytest


@pytest.fixture
def redis(mocker):
    return mocker.Mock(name='mock_redis')


@pytest.fixture
def test_data():
    return {"a": 1, "b": 2, "c": "hello"}
