from datetime import timedelta


def test_load_from_source(mocker, cache):
    assert cache["a"] == 101
    assert cache.load_from_source.call_count == 1

    assert cache["b"] == 102
    assert cache.load_from_source.call_count == 1

    assert sorted([x for x in cache])[2] == 'c'
    assert cache.load_from_source.call_count == 1


def test_error(cache, mocker, frozen_time):
    mocker.patch('time.sleep')
    mocker.patch.object(
        cache, 'load_from_source', side_effect=[
            Exception('Mock error'),
            cache.load_from_source(),
        ]
    )

    assert cache["a"] == 101
    assert cache.load_from_source.call_count == 2, 'Load should be called a second time after first call fails'


def test_init_ttl(cache, mocker):

    mocker.patch.object(cache, 'load_from_source', side_effect=[cache.load_from_source(), ])

    cache.cache_ttl = timedelta(hours=1)
    cache.reload()
    ttl = cache.resources_redis.ttl(cache.redis_key)
    assert ttl == timedelta(hours=1).total_seconds()

    cache.cache_ttl = timedelta(minutes=1)
    cache.reload()
    cache.check_initialization()
    ttl = cache.resources_redis.ttl(cache.redis_key)
    assert ttl == timedelta(minutes=1).total_seconds()
