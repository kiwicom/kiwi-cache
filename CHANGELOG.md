## [Unreleased]

## [0.3.0] – 2018-03-14

### Added

- Python 2.7 compatibility
- README, Changelog, Contributing
- DBTableResource
- Attempt limit of failed load_from_source calls
- Integration tests
- logging
- Instrumentation with datadog.DogStatsd

### Fixed

- Data in redis actually expires. Specified by `cache_ttl`, defaults to 10 \* `reload_ttl`.

## [0.1.2] – 2018-03-14

### Added

- AioKiwiCache
