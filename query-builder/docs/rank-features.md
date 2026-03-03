# Vespa Rank Features Reference

Complete catalog of built-in rank features organized by category. These features
are used in rank profile expressions to compute document relevance scores.

## Text Matching Features

### bm25(field)

BM25 text relevance score for a field. The standard probabilistic text ranking
function. Requires `index` mode on the field.

```
rank-profile my_profile {
    first-phase {
        expression: bm25(title) + 0.5 * bm25(body)
    }
}
```

Parameters `k1` and `b` can be tuned per field via `rank-properties`.

### nativeRank(field)

Combined native text relevance score that blends proximity, field match quality,
and term significance. A good general-purpose text feature.

```
expression: nativeRank(title) + nativeRank(body)
```

### nativeDotProduct(field)

Native dot product score component. Measures raw term frequency overlap.

```
expression: nativeDotProduct(title)
```

### nativeProximity(field)

Proximity component of nativeRank. Rewards terms appearing close together.

```
expression: nativeProximity(body)
```

### nativeFieldMatch(field)

Field match component of nativeRank. Rewards matching a larger proportion of
the field.

```
expression: nativeFieldMatch(title)
```

### fieldMatch(field)

Advanced string matching feature with many sub-features. Requires the field
to have `index` mode. Computes an optimal segmentation of the query against
the field.

```
expression: fieldMatch(title)
```

**Sub-features:**

| Feature | Description |
|---|---|
| `fieldMatch(f).completeness` | Fraction of query terms and field tokens matched |
| `fieldMatch(f).queryCompleteness` | Fraction of query terms matched in the field |
| `fieldMatch(f).fieldCompleteness` | Fraction of field tokens matched by query |
| `fieldMatch(f).orderness` | How well query term order is preserved |
| `fieldMatch(f).relatedness` | How closely matched terms are grouped |
| `fieldMatch(f).earliness` | How early in the field the match occurs |
| `fieldMatch(f).longestSequenceRatio` | Longest consecutive query match / query length |
| `fieldMatch(f).segmentProximity` | Proximity within matched segments |
| `fieldMatch(f).occurrence` | Weighted ratio of query terms occurring |
| `fieldMatch(f).absoluteOccurrence` | Occurrence scaled by field position |
| `fieldMatch(f).weightedOccurrence` | Occurrence weighted by term significance |
| `fieldMatch(f).significantOccurrence` | Occurrence weighted by IDF |
| `fieldMatch(f).weight` | Query term weight sum for matching terms |
| `fieldMatch(f).significance` | IDF significance of matching terms |
| `fieldMatch(f).matches` | Total number of term matches in field |
| `fieldMatch(f).degradedMatches` | Number of matches from degraded (fallback) matching |
| `fieldMatch(f).proximity` | Aggregate proximity score |
| `fieldMatch(f).head` | Number of tokens before first match |
| `fieldMatch(f).tail` | Number of tokens after last match |
| `fieldMatch(f).gaps` | Number of gaps in the matched segment |

### fieldLength(field)

Number of tokens in the field for the matched document.

```
expression: if (fieldLength(title) < 10, 1.0, 0.5)
```

### fieldTermMatch(field, term_index)

Match information for a specific query term in a specific field.

```
expression: fieldTermMatch(title, 0).occurrences
```

## Closeness / Distance Features (Nearest Neighbor)

### closeness(field)

Closeness score for nearest neighbor queries. Returns a value between 0 and 1
where 1 means identical vectors. Derived from the distance metric configured
on the field.

```
expression: closeness(embedding)
```

### closeness(label, name)

Closeness using a labeled nearestNeighbor operator. Use when your query has
multiple ANN operators.

```yql
select * from sources * where {targetHits: 50, label: "title_ann"}nearestNeighbor(title_emb, q_title)
```

```
expression: closeness(label, title_ann)
```

### distance(field)

Raw distance between the query vector and the document vector. Larger values
mean less similar. The inverse of closeness conceptually.

```
expression: 1.0 / (1.0 + distance(embedding))
```

### distance(label, name)

Raw distance using a labeled nearestNeighbor operator.

```
expression: distance(label, title_ann)
```

## Attribute Features

### attribute(field)

Direct access to the value of an attribute (in-memory) field. Works for
numeric single-value attributes.

```
expression: attribute(popularity)
expression: if (attribute(is_premium) == 1, 2.0, 1.0)
```

### attribute(field).count

Number of elements in a multi-value attribute (array or weighted set).

```
expression: attribute(tags).count
```

### attribute(field).weight

For weighted set attributes, the weight associated with a matched key.

## Freshness / Time Features

### freshness(field)

A value between 0 and 1 based on the age of a timestamp field. 1 means
brand-new, decaying toward 0 as the document ages. The decay rate is
configurable via `rank-properties`.

```
expression: freshness(publish_date)
```

Default half-life is roughly 1 hour. Configure via:

```
rank-properties {
    freshness(publish_date).maxAge: 86400    # seconds (24h)
    freshness(publish_date).halfResponse: 0.5
}
```

### age(field)

Raw age of a timestamp field in seconds. Use for custom decay functions.

```
expression: 1.0 / (1.0 + age(publish_date) / 86400)
```

## Query Features

### query(name)

Access a value or tensor sent with the query via `input.query(name)` or
`ranking.features.query(name)`.

```
expression: query(user_boost) * bm25(title)
```

For tensor values:

```
expression: sum(query(user_embedding) * attribute(item_embedding))
```

Query features are the primary mechanism for passing runtime parameters into
rank expressions (user context, embedding vectors, feature weights, etc.).

## Match Features

### matches

Total number of fields in which at least one query term matched.

```
expression: matches
```

### matches(field)

1 if the field had a match, 0 otherwise.

```
expression: if (matches(title), 2.0, 1.0)
```

## Term Features

### term(n).significance

IDF-based significance of the n-th query term (0-indexed).

```
expression: term(0).significance
```

### term(n).weight

The weight assigned to the n-th query term. Default is 100. Can be overridden
with annotations `{weight: 200}"important_term"`.

```
expression: term(0).weight / 100
```

### term(n).connectedness

The connectedness score between term n and its predecessor. Influences phrase
and proximity scoring.

## Document Features

### documentCount

Total number of documents in the index (across the local content node).

```
expression: log(documentCount)
```

Useful for manual IDF calculations or normalization.

## Global Phase Features

These features are only available in `global-phase` (second-phase re-ranking
across all content nodes).

### global features

In `global-phase`, you can reference `match-features` and `summary-features`
from the first phase, plus any additional global computations.

```
rank-profile hybrid {
    first-phase {
        expression: bm25(title)
    }
    match-features {
        bm25(title)
        bm25(body)
        closeness(embedding)
    }
    global-phase {
        rerank-count: 100
        expression: 0.3 * bm25(title) + 0.2 * bm25(body) + 0.5 * closeness(embedding)
    }
}
```

## Custom Functions as Features

Define reusable functions in a rank profile and reference them as features.

```
rank-profile my_profile {
    function text_score() {
        expression: 0.6 * bm25(title) + 0.4 * bm25(body)
    }
    function vector_score() {
        expression: closeness(label, semantic)
    }
    first-phase {
        expression: 0.5 * text_score + 0.5 * vector_score
    }
}
```

Functions can accept parameters:

```
function boosted_field(w) {
    expression: w * bm25(title)
}
```

## Debugging Rank Features

### match-features

Returned per hit in query results. Define in the rank profile to see feature
values used during ranking.

```
rank-profile debug_profile {
    first-phase {
        expression: bm25(title)
    }
    match-features {
        bm25(title)
        bm25(body)
        nativeRank(title)
        closeness(embedding)
        attribute(popularity)
        fieldMatch(title).completeness
    }
}
```

These appear in each hit under `matchfeatures` in the JSON response.

### summary-features

Similar to match-features but computed during the summary/fill phase. Useful
for features that are expensive and only needed for returned hits.

```
rank-profile my_profile {
    summary-features {
        bm25(title)
        fieldMatch(title)
        freshness(timestamp)
    }
}
```

### rank-features (all features)

Dump all available rank features for debugging. Very verbose output.

```
rank-profile dump_all {
    rank-features: true
}
```

Or via query parameter: `&ranking.listFeatures=true`

## Tensor Operations in Ranking

Vespa supports tensor math in rank expressions for advanced scoring.

### Common Tensor Operations

```
# Dot product of two vectors
expression: sum(query(embedding) * attribute(doc_embedding))

# Cosine similarity (assuming normalized vectors)
expression: sum(query(embedding) * attribute(doc_embedding))

# Euclidean distance
expression: sqrt(sum(map(query(embedding) - attribute(doc_embedding), f(x)(x * x))))

# Reduce: aggregate a tensor dimension
expression: reduce(attribute(scores), sum, category)

# Map: element-wise transformation
expression: map(attribute(score), f(x)(sigmoid(x)))

# Join: combine two tensors
expression: join(query(weights), attribute(features), f(x,y)(x * y))

# Argmax
expression: reduce(attribute(scores), max)

# Slice: extract specific cell
expression: attribute(embeddings){category: "sports"}

# Matmul via reduce
expression: reduce(query(vec) * attribute(matrix), sum, d1)

# L2 normalize
expression: query(embedding) / sqrt(reduce(query(embedding) * query(embedding), sum))
```

### Tensor Generate and Literal

```
# Constant tensor
expression: tensor(x[3]):[1.0, 2.0, 3.0]

# Generate
expression: tensor(x[10])(x)
```

Use tensor operations for cross-encoder scoring, learned sparse retrieval
weight application, multi-vector scoring, and custom similarity functions.
