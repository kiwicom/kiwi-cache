from typing import List  # pylint: disable=unused-import

import attr
from sqlalchemy import column, select, table
from sqlalchemy.orm.scoping import scoped_session
from sqlalchemy.sql.elements import ColumnElement

from . import KiwiCache


@attr.s
class SQLAlchemyResource(KiwiCache):
    """Caches selected columns or an entire table."""

    session = attr.ib(None, type=scoped_session, validator=attr.validators.instance_of(scoped_session))
    table_name = attr.ib(None, type=str, validator=attr.validators.instance_of(str))
    key = attr.ib(None, type=str, validator=attr.validators.optional(attr.validators.instance_of(str)))
    columns = attr.ib(None, type=List[str], validator=attr.validators.optional(attr.validators.instance_of(list)))
    where = attr.ib(
        None, type=ColumnElement, validator=attr.validators.optional(attr.validators.instance_of(ColumnElement))
    )

    @key.validator
    def mandatory_key_or_columns(self, attribute, value):
        """Validator that key or columns is mandatory."""
        if not value and not self.columns:
            raise ValueError("One of parameters ('columns' or 'key') must be set.")

    def _get_source_data(self):  # type: () -> list
        """Get data from db based on ``self.columns`` and ``self.key`` values.

        :return: rows with data
        """
        if self.columns == ["*"]:
            columns = ["*"]
        elif self.columns and self.key:
            columns = [column(name) for name in set(self.columns + [self.key])]
        elif self.columns:
            columns = [column(name) for name in self.columns]  # pylint: disable=not-an-iterable
        else:
            columns = [column(self.key)]
        query = select(columns)

        if self.where is not None:
            query = query.where(self.where)
        fetchall = self.session.execute(query.select_from(table(self.table_name))).fetchall()
        return [dict(key) for key in fetchall]

    def load_from_source(self):
        # type: () -> dict
        """Load data from database tables.

        ``self.key`` is required parameter.
        If you do not need key for response, override this method.

        :return: Resource data.
        """
        if not self.key:
            raise ValueError('Parameter "key" is required.')

        rows = self._get_source_data()
        return {row[self.key]: row for row in rows}
