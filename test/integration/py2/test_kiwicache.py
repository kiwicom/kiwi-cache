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
