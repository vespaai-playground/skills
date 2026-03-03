# Vespa Grouping and Aggregation Reference

Complete reference for Vespa's grouping and aggregation framework. Grouping is
appended to a YQL query using the pipe `|` operator and produces structured
aggregate results alongside (or instead of) individual hits.

## Basic Syntax

Grouping is appended after the WHERE clause using `|`:

```yql
select * from sources * where true | all(group(category) each(output(count())))
```

The result includes a `group-list` in the JSON response containing one group
per unique value of `category`, each with its count.

## Core Grouping Operations

### group(expression)

Defines what to group by. The expression can be a field name, a function,
or a computed expression.

```
all(group(category) each(output(count())))
all(group(fixedwidth(price, 100)) each(output(count())))
all(group(predefined(price, bucket[0,50>, bucket[50,100>, bucket[100,inf>)) each(output(count())))
```

### each(...)

Iterates over each group and defines what to compute or output for that group.
Contains `output()`, nested `group()`, or `each() as(label)`.

```
all(group(category) each(output(count(), sum(price))))
```

### all(...)

Top-level wrapper. Also used to define global aggregations across all results.

```
all(
    group(category) each(output(count()))
    output(count())
)
```

### output(aggregator, ...)

Specifies which aggregation values to produce for each group.

```
each(output(count(), sum(price), avg(price), min(price), max(price)))
```

### max(n)

Limits the number of groups returned.

```
all(group(category) max(10) each(output(count())))
```

### precision(n)

Controls how many groups are evaluated internally before applying `max(n)`.
Higher precision yields more accurate results at the cost of performance.
Default depends on `max(n)`.

```
all(group(category) max(10) precision(1000) each(output(count())))
```

**Rule of thumb:** Set `precision` to at least 2-3x `max` for accurate top-N
grouping, especially with distributed clusters.

### order(expression)

Controls the ordering of groups. Accepts aggregation expressions with `asc`
or `desc` direction. Default ordering is by the grouping expression ascending.

```
all(group(category) max(10) order(count()) each(output(count())))
all(group(category) max(10) order(-count()) each(output(count())))
all(group(brand) max(5) order(sum(revenue)) each(output(sum(revenue))))
```

Prefix `-` means descending. `order(count())` is ascending; `order(-count())`
is descending.

Multiple order criteria:

```
all(group(category) max(10) order(count(), -sum(price)) each(output(count(), sum(price))))
```

## Aggregation Functions

| Function | Description |
|---|---|
| `count()` | Number of documents in the group |
| `sum(expr)` | Sum of expression values |
| `avg(expr)` | Average of expression values |
| `min(expr)` | Minimum value |
| `max(expr)` | Maximum value |
| `xor(expr)` | Bitwise XOR of all values (useful for change detection) |
| `stddev(expr)` | Standard deviation |
| `summary(summary_class)` | Include hit summaries in each group |

```
each(output(count(), sum(price), avg(price), min(price), max(price), stddev(price)))
```

### summary() in groups

To include actual document hits within each group:

```
all(group(category) each(max(3) each(output(summary()))))
```

The inner `each(output(summary()))` produces up to `max(3)` hits per group.

## Grouping Expressions

### fixedwidth(field, width)

Buckets numeric values into fixed-width ranges.

```
all(group(fixedwidth(price, 50)) each(output(count())))
```

Produces groups like `[0, 50>`, `[50, 100>`, `[100, 150>`, etc.

### predefined(field, bucket[...], ...)

Manually defined buckets. Syntax uses `[` for inclusive and `>` for exclusive
on the upper bound.

```
all(group(predefined(price, bucket[0, 25>, bucket[25, 50>, bucket[50, 100>, bucket[100, inf>)) each(output(count())))
```

String buckets:

```
all(group(predefined(brand, bucket<"", "G">, bucket["G", "N">, bucket["N", "">)) each(output(count())))
```

### md5(field, bits)

Groups by the first N bits of the MD5 hash of the field value. Useful for
sampling or distributing into a fixed number of buckets.

```
all(group(md5(session_id, 64)) each(output(count())))
```

### cat(expr, expr)

Concatenates two expressions into a combined grouping key.

```
all(group(cat(brand, category)) each(output(count())))
```

### uca(field, locale)

Unicode Collation Algorithm sorting for string fields. Groups and sorts
according to locale-specific rules.

```
all(group(uca(name, "en_US")) each(output(count())))
```

### Mathematical expressions

Standard arithmetic on numeric fields:

```
all(group(price * quantity) each(output(count())))
all(group(fixedwidth(price / 100, 1)) each(output(count())))
```

### strlen(field)

Groups by string length.

```
all(group(strlen(title)) each(output(count())))
```

### tostring(expr) / toraw(expr)

Type conversion for grouping expressions.

```
all(group(tostring(category_id)) each(output(count())))
```

## Time-Based Grouping

Vespa provides time extraction functions for timestamp fields (seconds since
epoch).

| Function | Description |
|---|---|
| `time.year(field)` | Extract year |
| `time.month(field)` | Extract month (1-12, Jan-Dec) |
| `time.monthofyear(field)` | Same as `time.month` |
| `time.dayofmonth(field)` | Day of month (1-31) |
| `time.dayofweek(field)` | Day of week (0-6, Mon-Sun) |
| `time.dayofyear(field)` | Day of year (1-366) |
| `time.hourofday(field)` | Hour (0-23) |
| `time.minuteofhour(field)` | Minute (0-59) |
| `time.secondofminute(field)` | Second (0-59) |
| `time.date(field)` | Date as YYYY-MM-DD |

```yql
-- Documents per year
select * from sources * where true | all(group(time.year(timestamp)) each(output(count())))

-- Documents per month within each year
select * from sources * where true | all(group(time.year(timestamp)) each(group(time.month(timestamp)) each(output(count()))))

-- Hourly activity histogram
select * from sources * where true | all(group(time.hourofday(timestamp)) each(output(count())))

-- Daily groups
select * from sources * where sddocname contains "events" | all(group(time.date(created_at)) max(30) order(-max(created_at)) each(output(count())))
```

## Multi-Level Grouping

Nest `group()` inside `each()` for hierarchical aggregations.

```yql
-- Two-level: category then brand
select * from sources * where true
| all(group(category) max(10) each(output(count()) group(brand) max(5) each(output(count()))))

-- Three-level: year > month > day
select * from sources * where true
| all(group(time.year(ts)) each(
    output(count())
    group(time.month(ts)) each(
        output(count())
        group(time.dayofmonth(ts)) each(
            output(count())
        )
    )
  ))
```

## The `limit 0` Trick

When you only need aggregation results and no individual hits, set `limit 0`
in the YQL query:

```yql
select * from sources * where true limit 0 | all(group(category) each(output(count())))
```

This avoids the overhead of fetching and filling document summaries. The
grouping results are still fully computed.

## Continuations (Pagination of Groups)

When a grouping produces many groups, Vespa returns continuation tokens for
paginating through them.

The response includes `continuation` objects. To fetch the next page of groups:

```
&continuations=BBAAABEA...
```

Multiple continuations can be combined to navigate different levels
independently:

```
&continuations=BBAAABEA...&continuations=CCBBAABB...
```

Continuation tokens are opaque strings. Store them from the previous response
and pass them to the next request to advance pagination.

### Pagination workflow

1. Initial request: get first page of groups and a `this` + `next` continuation.
2. Next page: pass the `next` continuation token to get the subsequent groups.
3. Repeat until no `next` continuation is returned.

## each() vs all()

- `all(...)` is the root-level wrapper. It scopes the grouping to all matched
  documents. There is exactly one `all()` at the top level of the grouping
  expression.
- `each(...)` operates on each group produced by `group()`. It defines what
  to compute or output per group.

```
all(                               -- scope: all matched docs
    group(category)                -- split into groups by category
    max(10)                        -- return at most 10 groups
    each(                          -- for each category group:
        output(count(), avg(price))  -- compute these aggregates
    )
)
```

You can have multiple `each()` blocks at the same level with labels:

```
all(
    group(category) each(output(count())) as(by_category)
    group(brand) each(output(count())) as(by_brand)
)
```

This produces two parallel grouping result trees in a single query.

## Complete Examples

### Top categories with counts

```yql
select * from products where true limit 0
| all(group(category) max(20) order(-count()) each(output(count())))
```

### Average price per category, sorted by average price descending

```yql
select * from products where true limit 0
| all(group(category) max(50) order(-avg(price)) each(output(count(), avg(price), min(price), max(price))))
```

### Price histogram with fixed-width buckets

```yql
select * from products where category = "electronics" limit 0
| all(group(fixedwidth(price, 100)) each(output(count())))
```

### Time-series: daily order counts for the last 30 days

```yql
select * from orders where range(created_at, now() - 2592000, now()) limit 0
| all(group(time.date(created_at)) order(min(created_at)) each(output(count(), sum(total_amount))))
```

### Multi-level faceted search: category > brand with top hits

```yql
select * from products where default contains "laptop"
| all(
    group(category) max(5) order(-count()) each(
        output(count())
        group(brand) max(3) order(-count()) each(
            output(count(), avg(price))
            max(2) each(output(summary()))
        )
    )
  )
```

This returns: top 5 categories, within each the top 3 brands, within each the
top 2 actual product hits, along with counts and average prices.

### Parallel facets in one query

```yql
select * from products where default contains "phone" limit 0
| all(
    group(brand) max(10) order(-count()) each(output(count())) as(brands)
    group(predefined(price, bucket[0,200>, bucket[200,500>, bucket[500,1000>, bucket[1000,inf>)) each(output(count())) as(price_ranges)
    group(color) max(10) order(-count()) each(output(count())) as(colors)
  )
```

Returns three independent facet result trees (brands, price ranges, colors)
from a single query execution.

### Hourly activity heatmap by day of week

```yql
select * from events where range(timestamp, now() - 604800, now()) limit 0
| all(group(time.dayofweek(timestamp)) each(
    output(count())
    group(time.hourofday(timestamp)) each(output(count()))
  ))
```

Produces a 7x24 matrix of event counts suitable for a heatmap visualization.
