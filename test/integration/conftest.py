import os

from freezegun import freeze_time
import pytest
import redis as redislib
import testing.redis


@pytest.fixture(scope='session')
def redis_url():
    try:
        yield os.environ['TEST_REDIS_URL']
    except KeyError:
        with testing.redis.RedisServer() as test_redis:
            yield 'redis://{host}:{port}/{db}'.format(**test_redis.dsn())


@pytest.fixture
def redis(redis_url):  # pylint: disable=redefined-outer-name
    client = redislib.StrictRedis.from_url(redis_url)
    yield client
    client.flushall()


@pytest.fixture
def frozen_time():
    ft = freeze_time('2000-01-01 00:00:00')
    yield ft.start()
    ft.stop()
