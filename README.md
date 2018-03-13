# kiwi-cache

Cache for using Redis with diverse sources. Python 2.7 to 3.6 are supported. It is possible to use KiwiCache
for project with asyncio.

## Instalaltion

The simplest way to use kiwi-cache in your project is to install it with pip:

```
pip install kiwi-cache
```

## Example

An application for caching data from filesystem.

```
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

```
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

## Testing

To run all tests:

```
tox
```
