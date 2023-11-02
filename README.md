# redis-metric-helper

WARNING: This is still under active development.

Handles some of the more tedious parts of logging and reading metrics that get
logged to Redis. Counters, gauges and timeseries data. Requires RedisStack.


## Why does this package exist?

A helper to make writing/reading metrics to Redis more convenient.
Allows counters, gauges (including postive-only gauges) and timeseries data.


## Quickstart

1. Install the package:
   ```
   pip install redis-metric-helper
   ```

1. Initialize the package:
   ```python
   from metric_helper import metrics

   metrics.setup(
       connection_dict={
           'host': 'localhost', # Default
           'port': 6379, # Default
           'password': 'SuperS3kr!t',
           'socket_connect_timeout': 5, # Default
           'health_check_interval': 30, # Default
       },
       timezone='Africa/Johannesburg',
   )
   ```

1. Create/get a metric:
   ```python
   timeseries = metrics.get(
       'http_requests', # Redis key
       'timeseries', # Default
       round_timestamp_to='second',
   )
   timeseries.add_sample(
       value=1,
       duplicate_policy='sum',
       round_timestamp_to='second',
   )
   # Equivalent to add_sample() with above kwargs.
   timeseries.incr()

   counter = metrics.get('http_requests_total_count', 'counter')
   counter.incr()

   gauge = metrics.get('my_gauge', 'gauge')
   gauge.incr()

   pos_gauge = metrics.get('my_pos_gauge', 'pos_gauge')
   pos_gauge.incr()
   pos_gauge.decr()
   ```

1. Query the metric:
   ```python
   from datetime import datetime, timedelta

   end = datetime.now()
   start = end - timedelta(hours=24)
   results = timeseries.range(
       start=start, # Also allows "-"
       end=end, # Also allows "+"
       bucket_secs=3600, # Default
       empty=True, # Default
       agg_type='sum', # Default
       pipeline=None, # Default
   )

   count = counter.get()
   gauge_result = gauge.get()
   pos_gauge_result = pos_gauge.get()
   ```

1. Run commands in a Redis pipeline:
   ```python
   from metric_helper import pipeline
   results = pipeline([
       timeseries.range(start='-', end='+', bucket_secs=3600, defer=True),
       timeseries.range(start=start, end=end, bucket_secs=3600, defer=True),
       timeseries.add_sample(value=1, defer=True),
       timeseries.add_sample(value=1, defer=True),
       timeseries.incr(defer=True),
       counter.incr(defer=True),
   ])
   ```

1. Add compaction rules. To create a compaction rule for an hourly aggregate:
   ```python
   timeseries.add_rule(
       agg_type='sum',
       bucket_secs=3600,
       retention_days=120,
   )

   # If source key is named "http_requests", this will create a new key
   # named "http_requests--agg_3600_sum"
   source_key = 'http_requests'
   dest_key = f'{source_key}--agg_{bucket_secs}_{agg_type}'
   ```

   Or, optionally use the very opinionated `auto_add_rules` method:
   ```python
   timeseries.auto_add_rules()
   ```

   `auto_add_rules` will create five compaction rules equal to the following:
   ```python
   timeseries.add_rule(
       agg_type='sum',
       bucket_secs=60,
       retention_days=15,
   )
   timeseries.add_rule(
       agg_type='sum',
       bucket_secs=900,
       retention_days=31,
   )
   timeseries.add_rule(
       agg_type='sum',
       bucket_secs=3600,
       retention_days=367,
   )
   timeseries.add_rule(
       agg_type='sum',
       bucket_secs=86400,
       retention_days=367,
   )
   ```


## Recommendations on metric naming conventions

These are really just suggestions but a possible naming convention could be
something like this:
```
{prefix}:{metric_root_name}:{noun}:{noun_identifier}:{modifier_of_metric}
```

The prefix should be the package/component the metric is related to.

For example, for a component/app named "uploads" we might have a metric
named "filesize":
```
uploads:filesize
```

Then, all the filesizes for a specific user's uploads:
```
uploads:filesize:user:{user_id}
```

And then perhaps the filesize of all uploads by that user that were
identified as images:
```
uploads:filesize:user:{user_id}:images
```

For a metric named "failures":
```
uploads:failures
```

However, we might want to know how many timeouts occurred for any given
user:
```
uploads:failures:user:{user_id}
```
