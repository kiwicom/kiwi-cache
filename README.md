# kiwi-cache

Redis cache with pythonic dict-like interface just a method away!

You just need to implement `load_from_source` with desired resource and you are good to go! ✨
Python 2.7 to 3.6 are supported, also asyncio supported by AioKiwiCache.

## Installation

The simplest way to use kiwi-cache in your project is to install it with pip:

```
pip install kiwi-cache
```

## Example

An application for caching data from filesystem.

```python
import redis

from kw.cache import KiwiCache
...

class FileCache(KiwiCache):

    def load_from_source(self):
        cur.execute(
        """ SELECT * FROM example WHERE is_activate IS TRUE; """
        )
        return {row['id']: row for row in cur.fetchAll()}

if __name__=="__main__":
    redis = redis.StrictRedis(host='localhost', port=6379, db=0)
    cache = FileCache(resources_redis=redis)
    print(cache['file.cache'])
```

The KiwiCache supports asynchronous application with Redis. The similar issue looks following way:

```python
import asyncio
import aioredis

from kw.cache.aio import AioKiwiCache as KiwiCache
...

class FileCache(KiwiCache):
    async def load_from_source(self):
        await cur.execute(
        """ SELECT * FROM example WHERE is_activate IS TRUE; """
        )
        return {row['id']: row for row in cur.fetchAll()}

async def main_async():
    redis = await aioredis.create_redis('redis://localhost', loop=loop)
    cache = FileCache(resources_redis=redis)
    print(await cache.get('file.cache'))
    redis.close()
    await redis.wait_closed()

loop = asyncio.get_event_loop()
loop.run_until_complete(main_async())
loop.close()
```

If you want to cache data from DB table, you can use SQLAlchemyResource like this:

```python
import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from kw.cache.dbcache import SQLAlchemyResource

engine = create_engine(...)
scoped_db_session = scoped_session(sessionmaker(bind=engine))

redis = redis.StrictRedis(host='localhost', port=6379, db=0)

currency_rates = SQLAlchemyResource(redis, scoped_db_session, 'currency_rates', key='currency',
                                    columns=['currency', 'course'])
kiwi_airlines = SQLAlchemyResource(redis, scoped_db_session, 'kiwi_airlines', key='iatacode', columns=['*'])

# >>> print(kiwi_airlines['FR']['name'])
# 'Ryanair'
```

## Instrumentation

You can pass `datadog.DogStatsd` instance into KiwiCache as `statsd` argument:
Metric name is in format `kiwicache` with tags `name` and `status`:

- `name` is the class name of the subclassed cache
- `status` can be:
  - `redis_error` - error occured during saving/getting data from redis
  - `load_error` - `load_from_source` fails or doesn't return data
  - `success` - data is successfully loaded from source or from redis
- ideally pass `datadog.DogStatsd` with defined `namespace` to avoid collisions

## Data expiration

You can specify expiration of data in redis by overwriting `cache_ttl`. By default it is `reload_ttl * 10`,
which means that cached data in redis will be availible for some time even if `load_from_source` fails.

In case you have less expiration-sensitive data, you can specify `cache_ttl=None` which will disable
the expiration of cached data in redis. This can be very dangerous thing to do without proper alerting in place.

## Periodic cache refresh task

In case you want to avoid the performance degradation of your API workers caused
by the cache refill (especially in case of sync workers), you can add this snippet to your app as periodic task:

```python
from kw.booking import caches

def main():
    """Refresh resources data in Redis caches from source.

    Use this function in some periodic task in case you want to avoid performance
    degradation on your API workers.
    """
    for resource in caches.KiwiCache.instances:
        resource.refill_cache()


if __name__ == '__main__':
    main()
```

## Testing

To run all tests:

```
tox
```

Make sure to install Redis if you want the integration tests to work.
