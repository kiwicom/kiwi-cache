import attr
from mock import Mock
import pytest

from kw.cache.dbcache import SQLAlchemyResource


@attr.s
class FakeSQLAlchemyResource(SQLAlchemyResource):

    session = attr.ib(Mock(), type=Mock, validator=attr.validators.instance_of(Mock))


@pytest.mark.parametrize(
    "valid_params",
    [
        {},
        {"table_name": "name23"},
        {"key": "abc123", "columns": None},
        {"key": None, "columns": ["column1", "column2"]},
    ],
)
def test_init(redis, valid_params):
    params = {"resources_redis": redis, "table_name": "table", "key": "key"}
    params.update(valid_params)
    reasource = FakeSQLAlchemyResource(**params)
    for param, value in params.items():
        assert getattr(reasource, param) == value


@pytest.mark.parametrize(
    ("invalid_params", "error"),
    [
        ({"resources_redis": None}, TypeError),
        ({"session": None}, TypeError),
        ({"table_name": None}, TypeError),
        ({"table_name": 123}, TypeError),
        ({"key": 1}, TypeError),
        ({"columns": 33}, TypeError),
        ({"columns": "col"}, TypeError),
        ({"where": "value > 3"}, TypeError),
        ({"key": None, "columns": None}, ValueError),
    ],
)
def test_validators(redis, invalid_params, error):
    params = {"resources_redis": redis, "table_name": "table", "key": "key"}
    params.update(invalid_params)
    with pytest.raises(error):
        FakeSQLAlchemyResource(**params)
