## [Unreleased]

## [0.4.1] – 2018-05-30

### Changed

- Add tests to check functionality of ttl
- Validation for initial parameters
- Fix missing connection to Redis in SQLAlchemyResource

## [0.4.0] – 2018-04-26

### Changed

- Rename DBTableResource to SQLAlchemyResource

## [0.3.0] – 2018-04-25

### Added

- Python 2.7 compatibility
- README, Changelog, Contributing
- SQLAlchemyResource
- Attempt limit of failed load_from_source calls
- Integration tests
- logging
- Instrumentation with datadog.DogStatsd

### Fixed

- Data in redis actually expires. Specified by `cache_ttl`, defaults to 10 \* `reload_ttl`.

## [0.1.2] – 2018-03-14

### Added

- AioKiwiCache
