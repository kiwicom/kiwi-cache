import sys
from datetime import datetime, timedelta

from freezegun import freeze_time
import pytest

from kw.cache.aio import AioKiwiCache as uut

pytestmark = pytest.mark.skipif(sys.version_info < (3, 5), reason="requires python3.5")


@pytest.fixture(autouse=True)
def clean_instances_list():
    yield None
    uut.instances = []


@pytest.fixture
def redis(mocker):
    return mocker.stub(name='mock_redis')


@pytest.fixture
def instance():
    return uut(redis)


@pytest.fixture
def frozen_time():
    ft = freeze_time('2000-01-01 00:00:00')
    ft.start()
    yield ft
    ft.stop()


def test_init(redis):
    instance_one = uut(redis)
    instance_two = uut(redis)
    assert uut.instances == [instance_one, instance_two]


@pytest.mark.asyncio
async def test_maybe_reload(instance, frozen_time, mocker):
    reload = mocker.patch.object(instance, 'reload')

    await instance.maybe_reload()
    assert reload.call_count == 1

    instance._data = {1: 2}
    instance.expires_at = datetime.now() - timedelta(days=1)
    await instance.maybe_reload()
    assert reload.call_count == 2

    instance.expires_at = datetime.now() + timedelta(days=1)
    await instance.maybe_reload()
    assert reload.call_count == 2
