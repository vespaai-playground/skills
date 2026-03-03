# YQL Operators Reference

Complete reference for all YQL (Vespa Query Language) operators, their syntax,
annotations, and usage patterns.

## Text Matching Operators

### contains

Matches documents where a field contains a term or phrase.

```yql
select * from sources * where title contains "machine"
select * from sources * where title contains phrase("machine", "learning")
```

With annotations (e.g., controlling linguistics):

```yql
select * from sources * where title contains ({stem: false}"Machine")
select * from sources * where title contains ({normalizeCase: false, implicitTransforms: false}"ML")
```

### phrase

Matches an ordered sequence of terms with no intervening tokens.

```yql
select * from sources * where title contains phrase("neural", "network")
```

Equivalent to `contains phrase(...)`. Annotations:

```yql
select * from sources * where title contains ({stem: true}phrase("run", "fast"))
```

### near

Matches terms appearing within a window of N tokens (default 2), in any order.

```yql
select * from sources * where title contains near("machine", "learning")
select * from sources * where title contains ({distance: 5}near("machine", "learning"))
```

### onear (Ordered Near)

Like `near`, but terms must appear in the specified order.

```yql
select * from sources * where title contains onear("machine", "learning")
select * from sources * where title contains ({distance: 3}onear("deep", "neural", "network"))
```

### equiv

Treats multiple terms as equivalent for ranking purposes. Matches any of them
but ranks as if they were a single term.

```yql
select * from sources * where title contains equiv("car", "automobile", "vehicle")
```

### uri

Matches against URI-type fields with component awareness (scheme, host, port, path, query, fragment).

```yql
select * from sources * where myurl contains uri("https://example.com/path")
```

## Numeric and Range Operators

### Comparison Operators

Standard numeric comparisons: `=`, `>=`, `<=`, `>`, `<`.

```yql
select * from sources * where price >= 10 and price < 100
select * from sources * where year = 2024
select * from sources * where rating > 4.5
```

### range()

Explicit range function. Bounds are inclusive by default. Use `Infinity` or
`-Infinity` for open-ended ranges.

```yql
select * from sources * where range(price, 10, 100)
select * from sources * where range(price, 0, Infinity)
select * from sources * where range(year, 2020, 2024)
```

With annotations to control limit inclusivity:

```yql
select * from sources * where {bounds: "leftOpen"}range(price, 10, 100)
select * from sources * where {bounds: "rightOpen"}range(price, 10, 100)
select * from sources * where {bounds: "open"}range(price, 10, 100)
```

## Vector / ANN Operators

### nearestNeighbor

Approximate nearest neighbor search over a tensor field using HNSW index.

Full syntax with all annotations:

```yql
select * from sources * where {targetHits: 100, approximate: true, hnsw.exploreAdditionalHits: 200}nearestNeighbor(embedding_field, query_embedding)
```

**Annotations explained:**

| Annotation | Type | Default | Description |
|---|---|---|---|
| `targetHits` | int | required | Desired number of neighbors to retrieve from each content node |
| `approximate` | bool | `true` | Use HNSW index (`true`) or brute-force (`false`) |
| `hnsw.exploreAdditionalHits` | int | 0 | Extra candidates to explore in HNSW graph for better recall |
| `distanceThreshold` | double | none | Maximum distance; hits beyond this are discarded |
| `label` | string | none | Label for referencing this operator in rank features like `closeness(label, name)` |

```yql
-- Labeled nearest neighbor for use in ranking
select * from sources * where {targetHits: 50, label: "title_ann"}nearestNeighbor(title_embedding, q_title) or {targetHits: 50, label: "body_ann"}nearestNeighbor(body_embedding, q_body)
```

The query tensor must be passed as a rank feature via `input.query(query_embedding)`.

## Sparse / Weighted Matching Operators

### weakAnd

Efficient top-k retrieval operator. Skips documents unlikely to reach the top.
Use instead of OR when you want high recall with performance.

```yql
select * from sources * where {targetHits: 200}weakAnd(title contains "machine", title contains "learning", body contains "neural")
```

**When to use weakAnd vs AND:**
- `weakAnd` — recall-oriented; retrieves top-N documents matching any subset of terms, scored by term significance. Best for free-text search.
- `AND` — precision-oriented; requires all terms to match. Best for structured filters.

### wand (Parallel WAND)

Weighted AND for weighted set fields. Each term has an explicit weight.

```yql
select * from sources * where {targetHits: 100}wand(tags, {"machine": 80, "learning": 60, "AI": 100})
```

Operates on `weightedset` fields. More efficient than dotProduct for sparse
high-cardinality fields because it can skip low-scoring documents.

### dotProduct

Computes weighted dot product between query weights and a weighted set field.
All matching documents are scored, no early termination.

```yql
select * from sources * where dotProduct(tags, {"machine": 80, "learning": 60, "AI": 100})
```

Use when you need exact dot-product scores over all documents (e.g., in a
recall set already filtered by another operator).

### weightedSet

Matches documents containing any of the given weighted set items. Similar to
a multi-valued OR with weights.

```yql
select * from sources * where weightedSet(category_ids, {10: 1, 20: 1, 30: 1})
```

## Structural Matching Operators

### sameElement

Requires all conditions to match within the same struct element in an
array-of-struct field.

```yql
select * from sources * where persons contains sameElement(first_name contains "John", last_name contains "Smith", age > 30)
```

Without `sameElement`, conditions could match across different array elements.

## Geographic Operators

### geoLocation

Matches documents within a radius of a geographic coordinate.

```yql
select * from sources * where geoLocation(location_field, 37.7749, -122.4194, "10 km")
select * from sources * where geoLocation(location_field, 59.9139, 10.7522, "500 m")
select * from sources * where geoLocation(location_field, 48.8566, 2.3522, "50 mi")
```

Units: `m`, `km`, `mi` (miles), `deg` (degrees).

The field must be of type `position` in the schema.

## Predicate Matching

### predicate

Boolean matching on predicate-type fields. The document defines a boolean
expression; the query supplies attributes to evaluate.

```yql
select * from sources * where predicate(targeting_rules, {"gender": "female", "country": "us"}, {"age": 25})
```

Arguments: `predicate(field, string_attributes_map, range_attributes_map)`.

## Meta / Composition Operators

### rank

Controls which parts of the query drive recall vs. ranking. The first argument
is the recall expression (determines which documents match). Remaining arguments
contribute only to ranking features.

```yql
select * from sources * where rank(title contains "search", body contains "vector", tags contains "ML")
```

Only documents matching `title contains "search"` are retrieved. The other
expressions influence ranking scores but do not filter.

### nonEmpty

Wraps a query expression and suppresses it when it would be empty (e.g.,
when user input is blank). Prevents accidental match-all.

```yql
select * from sources * where nonEmpty(userInput(@query))
select * from sources * where nonEmpty(title contains ({prefix: true}userInput(@partial)))
```

### userQuery

Injects the query model's parsed query (from `query` parameter) into YQL.
Typically used with `type=any|all|phrase` parameters.

```yql
select * from sources * where userQuery()
```

Combined with filters:

```yql
select * from sources * where userQuery() and category = "electronics"
```

### userInput

Parameterized user input, parsed according to a default index and grammar.

```yql
select * from sources * where userInput(@freetext)
select * from sources * where title contains userInput(@title_query)
select * from sources * where {defaultIndex: "body", grammar: "all"}userInput(@q)
```

**Grammar options:** `raw`, `segment`, `web`, `all`, `any`, `phrase`, `weakAnd`.

Pass the actual value via query parameter: `&freetext=machine+learning`.

## Annotation Syntax

Annotations are JSON objects prefixed to an operator using curly braces.

```
{annotation_key: value, ...}operator(arguments)
```

Common annotation patterns:

```yql
-- Term annotations
select * from sources * where title contains ({weight: 200}"important")

-- Prefix matching
select * from sources * where title contains ({prefix: true}"mach")

-- Substring matching
select * from sources * where title contains ({substring: true}"learn")

-- Suffix matching
select * from sources * where title contains ({suffix: true}"ing")

-- Filter (do not influence ranking)
select * from sources * where title contains ({filter: true}"the")

-- Ranked (default true, explicitly include in ranking)
select * from sources * where title contains ({ranked: true}"search")
```

## Combining Operators

Use `and`, `or`, `not` (also `!`) to compose complex queries.

```yql
-- Basic boolean
select * from sources * where title contains "search" and category = "tech" and not region = "blocked"

-- Grouped boolean
select * from sources * where (title contains "vector" or title contains "embedding") and year >= 2023

-- Hybrid: ANN + filters + text
select * from sources * where (
    {targetHits: 100}nearestNeighbor(embedding, q_emb)
    or {targetHits: 200}weakAnd(default contains "semantic", default contains "search")
) and region = "us" and active = true

-- rank() with combined recall and ranking signals
select * from sources * where rank(
    {targetHits: 100}nearestNeighbor(embedding, q_emb),
    title contains "search",
    body contains "vector"
)
```

## Query Control Parameters

### timeout

Set query timeout in YQL:

```yql
select * from sources * where title contains "test" timeout 3000
```

Value is in milliseconds. Can also be set via `&timeout=3s` query parameter.

### limit and offset

Pagination:

```yql
select * from sources * where true limit 20 offset 40
```

### order by

Sorting:

```yql
select * from sources * where category = "books" order by price asc, rating desc
```

Ordering by rank score (default relevance):

```yql
select * from sources * where title contains "vespa" order by relevance()
```

### Query Tracing

Enable query tracing via query parameter (not YQL syntax):

```
&trace.level=3          -- trace execution plan
&trace.timestamps=true  -- include timing info
&trace.query=true       -- show parsed query tree
```

Useful for debugging operator behavior, understanding match/rank phases,
and identifying performance bottlenecks.
