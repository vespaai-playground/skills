---
name: "query-builder"
description: "Build Vespa YQL queries and design rank profiles. Covers YQL syntax, operators, grouping, rank-profile phases, ML model integration, and query tensor inputs."
---

# Vespa Query Builder

## Overview

Vespa queries use YQL (Vespa Query Language), a SQL-like language for search and relevance. A query flows through three stages: **matching** (YQL WHERE clause selects candidates), **ranking** (a rank profile scores each match), and **grouping** (optional aggregation into buckets). Queries are HTTP requests to `/search/` with YQL in the `yql` parameter.

For deeper reference, load these companion docs:
- `docs/yql-operators.md` -- exhaustive operator reference with edge-case notes.
- `docs/rank-features.md` -- full rank feature catalog with formulas.
- `docs/grouping.md` -- advanced grouping patterns and examples.

## YQL Quick Reference

```
select <fields> from <source> where <predicate> order by <attribute> limit <N> offset <M>
```

```yql
select * from sources * where true
select title, url from content where text contains "vespa"
select * from sources * where category = "news" order by publish_date desc limit 20 offset 40
```

When `<source>` is `sources *` or omitted, Vespa searches all content clusters.

## Operators

### Text Matching

**contains** -- matches a field against a token: `where title contains "search"`

**phrase** -- ordered, contiguous tokens:
```yql
where text contains phrase("new", "york", "city")
```

**near** -- tokens within a distance window (default 2):
```yql
where text contains ({distance: 5} near("open", "source"))
```

**onear** -- ordered near; tokens must appear in given order:
```yql
where text contains ({distance: 3} onear("neural", "network"))
```

**matches** -- regex matching: `where title matches "^intro.*guide$"`

### Boolean and Comparison Operators

```yql
where age > 18 and status = "active"
where price >= 10 and price <= 100
where !(category = "spam")
where color = "red" or color = "blue"
```

### nearestNeighbor (ANN)

Approximate nearest-neighbor search over a tensor field with an HNSW index:
```yql
where {targetHits: 100} nearestNeighbor(embedding, q_embedding)
where {targetHits: 100} nearestNeighbor(embedding, q_embedding) and category = "science"
```
- `embedding` is the document tensor field; `q_embedding` is the query tensor passed via `input.query(q_embedding)`.
- `targetHits` controls how many neighbors the index explores.

### sameElement

Matches within a single struct/map element, preventing cross-element matching:
```yql
where persons contains sameElement(first_name contains "john", last_name contains "smith")
```

### rank

Separates recall (first argument) from ranking signals (remaining). Only the first operand retrieves documents:
```yql
where rank(title contains "vespa", description contains "search", tags contains "open-source")
```

### weakAnd / wand

Weak AND evaluates a large OR efficiently, skipping documents that cannot beat the top-k threshold:
```yql
where {targetHits: 200} weakAnd(title contains "big", title contains "data", title contains "analytics")
```
`wand` is the weighted variant on a single weighted set field:
```yql
where {targetHits: 200} wand(tags, {"machine": 80, "learning": 70, "ai": 60})
```

### dotProduct and weightedSet

**dotProduct** -- dot product between query weights and a document weighted set (ranking signal, not a filter):
```yql
where dotProduct(tags, {"python": 1, "java": 2, "rust": 3})
```
**weightedSet** -- filter; matches documents whose weighted set contains at least one key:
```yql
where weightedSet(tags, {"ml": 1, "ai": 1})
```

### geoLocation

Geographic filtering on a `position` field:
```yql
where geoLocation(location, 37.7749, -122.4194, "10 km")
```

### predicate

Matches predicate fields (ad targeting, access control):
```yql
where predicate(targeting, {"gender": ["male"], "age": ["25"]}, {"bid_price": 120})
```

### userQuery and userInput

**userQuery()** -- inserts the `query` parameter, parsed per `model.type` (all, any, phrase, weakAnd):
```yql
select * from sources * where userQuery()
```
Passed with: `&query=machine+learning&model.type=weakAnd`

**userInput(@param)** -- parameterized substitution (prevents YQL injection):
```yql
select * from sources * where title contains userInput(@searchterm)
```
Passed with: `&searchterm=distributed+systems`

## Pagination and Sorting

```yql
select * from sources * where true limit 25 offset 0
select * from sources * where category = "electronics" order by price asc, rating desc
```

- `limit` -- number of results to return. `offset` -- results to skip (zero-based).
- Fields in `order by` must be `attribute` in the schema. Deep pagination is expensive.
- Without `order by`, results are ordered by descending rank score.

## Grouping

Grouping uses pipe syntax appended to a YQL select, aggregating matched documents.

### Basic Syntax and Structure

```yql
select * from sources * where true | all(group(category) each(output(count())))
```

- `all(...)` -- operates on the full result set (outermost wrapper).
- `each(...)` -- operates on each group; nests inside `all(...)`.

### Aggregation Functions

`count()`, `sum(field)`, `avg(field)`, `min(field)`, `max(field)`, `xor(field)`

### Multi-Level Grouping

```yql
select * from sources * where true |
  all(group(category) each(output(count()) all(group(brand) each(output(count(), avg(price))))))
```

### Grouping Controls

Use `limit 0` to suppress hits and return only aggregation data:
```yql
select * from sources * where true limit 0 | all(group(year) each(output(count(), sum(revenue))))
```

Use `max(N)` to cap groups, `precision(N)` to increase accuracy, `order(...)` to sort:
```yql
select * from sources * where true |
  all(group(category) max(10) precision(1000) order(-count()) each(output(count())))
```

## Rank Profile Design

### Basic Structure

```sd
rank-profile default {
    first-phase {
        expression: bm25(title) + 0.5 * bm25(body)
    }
}
```

### Three Ranking Phases

**first-phase** -- evaluated on every match; must be cheap.
**second-phase** -- re-ranks top N from first phase; can use expensive features.
**global-phase** -- runs on the stateless container after merging from all content nodes; enables cross-node re-ranking and `normalize_linear`.

```sd
rank-profile two-phase {
    first-phase {
        expression: bm25(title) + bm25(body)
    }
    second-phase {
        expression: 0.7 * bm25(title) + 0.3 * bm25(body) + 0.5 * freshness(timestamp)
        rerank-count: 100
    }
}

rank-profile hybrid {
    inputs {
        query(q_embedding) tensor<float>(x[384])
    }
    first-phase {
        expression: closeness(field, embedding)
    }
    global-phase {
        expression: normalize_linear(closeness(field, embedding)) + normalize_linear(bm25(title))
        rerank-count: 200
    }
}
```

### Query Tensor Inputs in Rank Profiles

```sd
rank-profile semantic {
    inputs {
        query(q_embedding) tensor<float>(x[384])
        query(user_profile) tensor<float>(cat[10])
        query(boost_weight) double
    }
    first-phase {
        expression: closeness(field, embedding) + query(boost_weight) * attribute(popularity)
    }
}
```

### Functions and Inheritance

Functions define reusable sub-expressions. `inherits` lets a child profile extend a parent:

```sd
rank-profile base {
    function text_score() {
        expression: bm25(title) + bm25(body)
    }
    first-phase {
        expression: text_score
    }
}

rank-profile boosted inherits base {
    function text_score() {
        expression: 2.0 * bm25(title) + bm25(body)
    }
    second-phase {
        expression: text_score + freshness(timestamp)
        rerank-count: 50
    }
}
```

### match-features and summary-features

Inspect which rank features contributed to each hit:

```sd
rank-profile debug inherits default {
    match-features {
        bm25(title)
        bm25(body)
        closeness(field, embedding)
    }
    summary-features {
        bm25(title)
        attribute(popularity)
    }
}
```

`match-features` are available in second-phase, global-phase, and results. `summary-features` are computed during the summary fill phase.

## ML Model Integration

### ONNX Models

```sd
rank-profile onnx-ranker {
    onnx-model my_model {
        file: models/ranker.onnx
        input input_ids: my_input_tensor
        output logits: my_output
    }
    function my_input_tensor() {
        expression: tensor<float>(d0[1], d1[10])(...)
    }
    second-phase {
        expression: onnx(my_model).my_output
        rerank-count: 100
    }
}
```

### XGBoost and LightGBM

```sd
rank-profile xgb-ranker {
    second-phase {
        expression: xgboost("models/xgb_model.json")
        rerank-count: 200
    }
}

rank-profile lgbm-ranker {
    second-phase {
        expression: lightgbm("models/lgbm_model.json")
        rerank-count: 200
    }
}
```

Export models as JSON under `models/`. Feature names must match Vespa rank feature names.

## Rank Feature Catalog

| Feature | Description |
|---|---|
| `bm25(field)` | BM25 text relevance score |
| `nativeRank(field)` | Vespa's default text relevance feature |
| `closeness(field, tensor_field)` | Inverse distance for ANN; 1.0 = identical |
| `attribute(field)` | Raw attribute value (numeric or enum) |
| `freshness(field)` | Time-decay score; 1.0 for now, decays for older timestamps |
| `fieldMatch(field)` | Composite text match quality |
| `fieldMatch(field).completeness` | Fraction of query terms matched |
| `fieldMatch(field).proximity` | Closeness of matched terms to each other |
| `query(name)` | Query parameter as rank feature |
| `term(n).significance` | IDF-based significance of nth query term |
| `matchCount(field)` | Number of matched query terms |
| `dotProduct(field, vector)` | Dot product with document weighted set |
| `elementSimilarity(field)` | Similarity for array-of-struct fields |

For the full catalog, load `docs/rank-features.md`.

## Passing Query Tensors

Tensors are passed via `input.query(name)` in the query request.

**Dense tensor:**
```json
{ "input.query(q_embedding)": [0.1, 0.05, -0.23, "..."] }
```
Declared as: `query(q_embedding) tensor<float>(x[384])`

**Sparse tensor (mapped):**
```json
{ "input.query(user_tags)": {"cells": [{"address": {"tag": "ml"}, "value": 1.0}]} }
```
Declared as: `query(user_tags) tensor<float>(tag{})`

**Mixed tensor:**
```json
{ "input.query(preferences)": {"blocks": {"sports": [0.1, 0.2], "tech": [0.5, 0.3]}} }
```
Declared as: `query(preferences) tensor<float>(category{}, feature[64])`

## Common Gotchas

**1. Attribute fast-search for filtering** -- fields in WHERE filters need `attribute: fast-search` for B-tree indexing, otherwise Vespa does a linear scan. Add `rank: filter` for filter-only fields.
```sd
field category type string {
    indexing: attribute | summary
    attribute: fast-search
    rank: filter
}
```

**2. weakAnd is not strict AND** -- it optimizes OR, not AND. `targetHits` is a target, not a guarantee. Use explicit `and`/`or` if you need precise match counts.

**3. Mixing text and vector search** -- use `or` for union retrieval, `rank` to use ANN only as a scoring signal:
```yql
select * from articles where title contains "neural" or {targetHits: 100} nearestNeighbor(embedding, q_embedding)
select * from articles where rank(title contains "neural", {targetHits: 100} nearestNeighbor(embedding, q_embedding))
```

**4. Field type requirements** -- `contains` works only on `index` fields. Comparison operators (`=`, `>`, `<`) require `attribute` fields. `nearestNeighbor` needs a tensor field with HNSW `index`.

**5. Default ranking** -- without `ranking.profile`, Vespa uses the profile named `default`. If none exists, documents score 0.

**6. Timeout** -- default is 500ms. Set `"timeout": "5s"` for expensive queries (ONNX inference, deep grouping).
