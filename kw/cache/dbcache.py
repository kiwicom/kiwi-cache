from sqlalchemy import column, table, select
from sqlalchemy.orm.scoping import scoped_session  # pylint: disable=unused-import
from sqlalchemy.sql.elements import ColumnElement  # pylint: disable=unused-import

from . import KiwiCache


class DBTableResource(KiwiCache):
    """Caches an entire table."""

    def __init__(self, session, table_name, key=None, columns=None, where=None):  # pylint: disable=too-many-arguments
        # type: (scoped_session, str, Optional[str], Optional[List[str]], Optional[ColumnElement]) -> None
        if not columns and not key:
            raise ValueError('One of parameters ("columns" or "key") must be set.')

        self.session = session
        self.table_name = table_name
        self.columns = columns
        self.key = key
        self.where = where
        super(DBTableResource, self).__init__()
        self.name = 'table-' + self.table_name

    def _get_source_data(self):  # type: () -> list
        """Get data from db based on ``self.columns`` and ``self.key`` values.

        :return: rows with data
        """
        if self.columns == ['*']:
            columns = self.columns
        elif self.columns and self.key:
            columns = [column(name) for name in set(self.columns + [self.key])]
        elif self.columns:
            columns = [column(name) for name in self.columns]
        elif self.key:
            columns = [column(self.key)]
        query = select(columns)

        if self.where is not None:
            query = query.where(self.where)
        fetchall = self.session.execute(query.select_from(table(self.table_name))).fetchall()
        return [dict(key) for key in fetchall]

    def load_from_source(self):  # type: () -> dict
        """Load data from database tables.

        ``self.key`` is required parameter.
        If you do not need key for response, override this method.

        :return: Resource data.
        """
        if not self.key:
            raise ValueError('Parameter "key" is required.')

        rows = self._get_source_data()
        return {row[self.key]: row for row in rows}
