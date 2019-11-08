## [Unreleased]

### Changed

## [0.4.5] – 2019-10-08

### Added

- setting for possibility having empty data in source

### Changed

- upgrade requirements
- release of refill lock after loading from source
- prolonging local data when we cannot reload them
- catching of all RedisErrors instead of ConnectionError - breaking change,
  if you want the original behavior then you can override `_process_cache_error` method
- fix infinite loop in case of RedisError with max_attemps > 0

## [0.4.4] – 2018-10-09

### Added

- better docstring for `BaseKiwiCache` and `KiwiCache`

### Changed

- fix initial value of `expires_at` attribute of `KiwiCache`
- fix `KiwiCache` data prolong if local `_data` is filled
- change `instances` array to dict

## [0.4.3] – 2018-09-03

### Added

- Black check for gitlab CI

### Changed

- Remove using arrow
- Remove using attrs for class attributes
- Format docs by Black project

## [0.4.2] – 2018-08-16

- Generalize KiwiCache and use attrs
- Format of code by Black project

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
