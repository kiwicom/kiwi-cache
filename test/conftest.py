from freezegun import freeze_time
import pytest


@pytest.fixture
def frozen_time():
    with freeze_time("2000-01-01 00:00:00", ignore=["_pytest.runner"]) as ft:
        yield ft
