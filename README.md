# redis-metric-helper

WARNING: This is still under active development.

Handles some of the more tedious parts of logging and reading metrics that get
logged to Redis. Counters, gauges and timeseries data. Requires RedisStack.


## Why does this package exist?

A helper to make writing/reading metrics to Redis more convenient. Requires
`RedisStack`. Allows counters, gauges (including postive-only gauges) and
timeseries data.
