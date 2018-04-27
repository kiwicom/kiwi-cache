from kw.cache.dbcache import SQLAlchemyResource


def test_init(redis, test_data, mocker):
    db_connection = mocker.Mock()
    query = mocker.Mock()
    mocker.patch.object(query, 'fetchall', return_value=[test_data])
    mocker.patch.object(db_connection, 'execute', return_value=query)

    SQLAlchemyResource(redis, db_connection, 'table_name', key='key', columns=['*'])
