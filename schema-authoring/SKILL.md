---
name: "schema-authoring"
description: "Writing, validating, and evolving Vespa .sd schema files — covers field types, indexing pipelines, match modes, tensors, rank profiles, structs, fieldsets, and common pitfalls."
---

# Vespa Schema Authoring

## Overview

A Vespa **schema** (`.sd` file) defines a document type: its fields, indexing behavior, matching rules, and ranking configuration. Schemas live under `schemas/` in a Vespa application package.

This skill applies when the user needs to create, modify, or troubleshoot `.sd` schema files -- including field definitions, indexing pipelines, match modes, tensor/HNSW config, rank profiles, structs, fieldsets, or document references.

> **For deeper detail**, load `docs/field-types.md` and `docs/schema-patterns.md` from this skill's directory.

## Quick Reference

| Concept | Purpose | Syntax |
|---|---|---|
| Field | Named, typed data element | `field title type string { ... }` |
| Indexing pipeline | Controls storage/indexing | `indexing: summary \| index` |
| Match mode | How queries match content | `match { exact }` |
| Attribute | In-memory column for sort/group/filter | `indexing: attribute` |
| Index | Inverted index for text search | `indexing: index` |
| Summary | Included in result output | `indexing: summary` |
| Tensor | Multi-dimensional numeric data | `tensor<float>(x[384])` |
| HNSW | ANN index on tensors | `index { hnsw { ... } }` |
| Struct | Composite sub-type | `struct address { ... }` |
| Fieldset | Virtual group of fields | `fieldset default { fields: title, body }` |
| Rank profile | Scoring configuration | `rank-profile bm25 { ... }` |
| Reference | Parent-child document link | `reference<parent_schema>` |

## Minimal Skeleton

```sd
schema my_doc {
    document my_doc {
        field title type string {
            indexing: summary | index
            match: text
        }
    }
    fieldset default { fields: title }
    rank-profile default {
        first-phase { expression: nativeRank(title) }
    }
}
```

The outer `schema` name and inner `document` name must match.

## Field Types

### Primitive Types

| Type | Description | Typical indexing |
|---|---|---|
| `string` | UTF-8 text | `summary \| index` or `summary \| attribute` |
| `int` | 32-bit signed integer | `summary \| attribute` |
| `long` | 64-bit signed integer | `summary \| attribute` |
| `float` | 32-bit IEEE 754 | `summary \| attribute` |
| `double` | 64-bit IEEE 754 | `summary \| attribute` |
| `bool` | Single-bit boolean | `summary \| attribute` |
| `byte` | 8-bit signed integer | `summary \| attribute` |
| `position` | Lat/lon geo pair (microdegrees) | `summary \| attribute` |
| `uri` | URL with host/path tokenization | `summary \| index` |
| `predicate` | Boolean constraint expressions | `summary \| attribute` |
| `raw` | Opaque byte blob, not searchable | `summary` |

### Reference and Tensor Types

| Type | Description |
|---|---|
| `reference<schema_name>` | Foreign key for parent-child joins via `import field` |
| `tensor<float>(x[N], y{})` | Multi-dimensional tensor; indexed `[N]` and mapped `{}` dims |

### Collection Types

- **`array<T>`** -- Ordered list. Supports `index` and `attribute`.
- **`weightedset<T>`** -- Set with integer weights. T must be `string`, `int`, or `long`.
- **`map<K, V>`** -- Key-value map. K must be `string`, `int`, or `long`. Index sub-fields via `struct-field`.

```sd
field tags type array<string> {
    indexing: summary | index
}
field scores type weightedset<string> {
    indexing: summary | attribute
}
field properties type map<string, string> {
    indexing: summary
    struct-field key   { indexing: attribute   match: exact }
    struct-field value { indexing: attribute }
}
```

## Indexing Pipeline

A field's `indexing` statement is a `|`-separated pipeline of directives.

- **`index`** -- Disk-backed inverted index. Required for `match: text` and linguistic search. Supports stemming, normalization, proximity data.
- **`attribute`** -- In-memory column store. Required for sorting, grouping, filtering, and access in ranking expressions.
- **`summary`** -- Include in search result output. Without this, field values are not returned.

### Common Combinations

```sd
field title type string       { indexing: summary | index }              # text search + results
field category type string    { indexing: summary | attribute            # filter + results
                                match: exact   rank: filter }
field description type string { indexing: summary | index | attribute }  # search + filter + results
field quality type double     { indexing: attribute }                    # ranking only
field html type string        { indexing: summary }                     # retrieval only
```

### Attribute Modifiers

```sd
attribute {
    fast-search    # B-tree posting list for fast filtering
    fast-access    # keep in memory on all nodes
    paged          # allow paging to disk to save memory
}
```

### Input Expressions

Transform data inline: `lowercase`, `normalize`, `tokenize`, `to_int`, `to_long`, `to_string`, `to_array`, `set_language`.

```sd
field title_lower type string {
    indexing: input title | lowercase | summary | index
}
```

## Match Modes

| Mode | Behavior | Use case |
|---|---|---|
| `text` | Tokenized, stemmed, normalized (default) | Free-text search |
| `word` | Exact single-token, no stemming | Tags, labels, enums |
| `exact` | Entire value must match exactly | IDs, SKUs, emails |
| `prefix` | Prefix matching | Autocomplete |
| `substring` | Any substring (expensive) | Prefer `gram` instead |
| `gram` | Character n-gram index | CJK text, substring search |
| `cased` | Case-sensitive matching | Case-sensitive identifiers |

```sd
field body type string     { indexing: summary | index   match: text }
field sku type string      { indexing: summary | index   match: exact }
field suggest type string  { indexing: summary | index   match: prefix }
field cjk type string      { indexing: summary | index   match { gram   gram-size: 2 } }
```

Note: `match: word` and `match: exact` require `index`. For attribute-only exact matching, use `fast-search` and query with the `=` prefix operator.

## Tensor Fields and HNSW Configuration

### Tensor Type Syntax

Format: `tensor<value-type>(dimension-list)`. Value types: `float`, `double`, `int8`, `bfloat16`. Indexed dims: `x[384]`. Mapped dims: `x{}`. Mixed: `tensor<float>(cat{}, x[128])`.

```sd
field embedding type tensor<float>(x[384]) {
    indexing: summary | attribute
    attribute {
        distance-metric: angular
    }
    index {
        hnsw {
            max-links-per-node: 16
            neighbors-to-explore-at-insert: 200
        }
    }
}
```

### Distance Metrics

| Metric | When to use |
|---|---|
| `euclidean` | General-purpose; magnitude matters |
| `angular` | Direction matters; any normalization |
| `dotproduct` | Pre-normalized vectors; max inner product |
| `prenormalized-angular` | Already L2-normalized vectors (saves computation) |
| `hamming` | Binary hash codes, int8 quantized vectors |
| `geodegrees` | Geographic coordinate points |

### HNSW Parameters

| Parameter | Default | Guidance |
|---|---|---|
| `max-links-per-node` | 16 | Higher = better recall, more memory. Range: 8-32. |
| `neighbors-to-explore-at-insert` | 200 | Higher = better graph, slower feeding. Range: 100-500. |

Query-time exploration is controlled by `hnsw.exploreAdditionalHits` and `approximate` query parameters, not by the schema.

## Struct Types

Define composite types with `struct` inside `document`. Use `struct-field` to index inner fields.

```sd
struct address {
    field street type string {}
    field city type string {}
    field country type string {}
}
field warehouse type address {
    indexing: summary
    struct-field city    { indexing: attribute   match: exact }
    struct-field country { indexing: attribute   match: exact }
}
field locations type array<address> {
    indexing: summary
    struct-field city { indexing: attribute }
}
```

Structs can be used inside `array<>` and `map<>` collections.

## Fieldsets

Combine fields for unified search. Declared at `schema` level, outside `document`.

```sd
fieldset default {
    fields: title, body, description
}
```

All fields in a fieldset must be the same type (string) with compatible match/indexing modes.

## Rank Profiles

### Structure and Key Elements

```sd
rank-profile hybrid inherits default {
    inputs {
        query(query_embedding) tensor<float>(x[384])
        query(text_weight) double: 0.7
    }
    function text_score() {
        expression: bm25(title) * 2 + bm25(body)
    }
    function vector_score() {
        expression: closeness(field, embedding)
    }
    first-phase {
        expression: text_score
    }
    second-phase {
        expression: query(text_weight) * normalize_linear(text_score) + (1 - query(text_weight)) * normalize_linear(vector_score)
        rerank-count: 200
    }
    match-features {
        text_score
        vector_score
    }
}
```

| Element | Purpose |
|---|---|
| `inherits` | Inherit from another rank profile |
| `inputs` | Query-time inputs (tensors, scalars with defaults) |
| `first-phase` | Score all matching documents |
| `second-phase` | Re-score top N from first phase |
| `rerank-count` | N for second-phase (default 100) |
| `function` | Reusable sub-expression |
| `match-features` | Features returned in results for debugging |
| `summary-features` | Features in full document summaries |
| `constants` | Named numeric constants |
| `global-phase` | Cross-node re-ranking (Vespa 8+) |

Rank profiles support **inheritance** -- child profiles override or extend parent definitions via `inherits`.

## Schema Evolution Warnings

**Reserved field names** (cause conflicts): `documentid`, `relevance`, `sddocname`.

**Type changes:** Changing a field type (e.g., `string` to `int`) requires reindexing and `validation-overrides.xml`. Widening (`int` to `long`) is safe; narrowing is not.

**Removing fields:** First remove all references in rank profiles, fieldsets, and summaries, then remove the field. Stop feeding the field before removal.

**Adding fields:** Safe on a running system. Existing documents get empty/default values. Attribute fields consume memory even when empty.

## Complete Example: E-Commerce Product Schema

```sd
schema product {
    document product {
        struct price_range {
            field min type double {}
            field max type double {}
            field currency type string {}
        }
        field product_id type string {
            indexing: summary | attribute
            attribute: fast-search
        }
        field title type string {
            indexing: summary | index
            index: enable-bm25
            bolding: on
        }
        field description type string {
            indexing: summary | index
            index: enable-bm25
            summary: dynamic
        }
        field brand type string {
            indexing: summary | index | attribute
            match: word
            attribute: fast-search
            rank: filter
        }
        field category type array<string> {
            indexing: summary | attribute
            attribute: fast-search
        }
        field tags type weightedset<string> {
            indexing: summary | attribute
        }
        field price type double {
            indexing: summary | attribute
            attribute: fast-search
        }
        field sale_price type price_range {
            indexing: summary
            struct-field min      { indexing: attribute }
            struct-field max      { indexing: attribute }
            struct-field currency { indexing: attribute  match: exact }
        }
        field in_stock type bool {
            indexing: summary | attribute
            attribute: fast-search
            rank: filter
        }
        field rating type float {
            indexing: summary | attribute
        }
        field review_count type int {
            indexing: summary | attribute
        }
        field created_at type long {
            indexing: summary | attribute
            attribute: fast-search
        }
        field image_url type uri {
            indexing: summary
        }
        field embedding type tensor<float>(x[384]) {
            indexing: summary | attribute
            attribute {
                distance-metric: prenormalized-angular
            }
            index {
                hnsw {
                    max-links-per-node: 16
                    neighbors-to-explore-at-insert: 200
                }
            }
        }
        field attributes type map<string, string> {
            indexing: summary
            struct-field key   { indexing: attribute  match: exact }
            struct-field value { indexing: attribute }
        }
    }
    fieldset default {
        fields: title, description
    }
    rank-profile default {
        first-phase {
            expression: nativeRank(title) + nativeRank(description)
        }
    }
    rank-profile bm25_ranking inherits default {
        first-phase {
            expression: bm25(title) * 3 + bm25(description)
        }
    }
    rank-profile semantic inherits default {
        inputs {
            query(query_embedding) tensor<float>(x[384])
        }
        first-phase {
            expression: closeness(field, embedding)
        }
    }
    rank-profile hybrid inherits default {
        inputs {
            query(query_embedding) tensor<float>(x[384])
            query(text_weight) double: 0.6
            query(semantic_weight) double: 0.4
        }
        function text_score() {
            expression: bm25(title) * 3 + bm25(description)
        }
        function semantic_score() {
            expression: closeness(field, embedding)
        }
        first-phase {
            expression: text_score
        }
        second-phase {
            expression {
                query(text_weight) * normalize_linear(text_score) +
                query(semantic_weight) * normalize_linear(semantic_score)
            }
            rerank-count: 200
        }
        match-features {
            bm25(title)
            bm25(description)
            closeness(field, embedding)
        }
    }
    rank-profile personalized inherits hybrid {
        inputs {
            query(query_embedding) tensor<float>(x[384])
            query(text_weight) double: 0.4
            query(semantic_weight) double: 0.3
            query(freshness_weight) double: 0.15
            query(popularity_weight) double: 0.15
        }
        function freshness_score() {
            expression: freshness(created_at)
        }
        function popularity() {
            expression: if(review_count > 0, log10(review_count) * attribute(rating), 0)
        }
        second-phase {
            expression {
                query(text_weight) * normalize_linear(text_score) +
                query(semantic_weight) * normalize_linear(semantic_score) +
                query(freshness_weight) * freshness_score +
                query(popularity_weight) * normalize_linear(popularity)
            }
            rerank-count: 300
        }
    }
}
```

## Gotchas and Common Mistakes

**1. Forgetting `index: enable-bm25`.** The `bm25(field)` rank feature returns 0 without it.

```sd
# Wrong -- bm25(title) returns 0
field title type string { indexing: summary | index }
# Correct
field title type string { indexing: summary | index   index: enable-bm25 }
```

**2. `match: exact` without `index`.** The `match` directive controls how the *index* processes terms. On attribute-only fields it has no effect. Use `fast-search` + the `=` query prefix for attribute exact matching.

**3. Schema/document name mismatch.** Both names must be identical or deployment fails.

**4. Tensor dimension mismatch.** Query and document tensors must share exact dimension names and sizes (`x[384]` in both, not `d[384]` vs `x[384]`).

**5. Memory pressure from attributes.** Every attribute is in-memory. Use `attribute: paged` for large or rarely-accessed attribute fields.

**6. Type changes on live systems.** Requires reindexing and `validation-overrides.xml`.

**7. Missing `summary`.** Fields without `summary` in their indexing pipeline are not returned in results.

**8. `raw` is not searchable.** Only use for binary blobs that need storage and retrieval.

**9. Weightedset type restrictions.** Element type must be `string`, `int`, or `long`.

**10. Reference fields require `attribute` only.** No `index`. Use `import field` for parent fields:

```sd
schema child {
    document child {
        field parent_ref type reference<parent> { indexing: attribute }
    }
    import field parent_ref.name as parent_name {}
}
```

## Agent Instructions

When working with Vespa schemas:

1. Validate that `schema` and `document` names match.
2. Ensure every field used in `bm25()` ranking has `index: enable-bm25`.
3. Confirm tensor dimensions are consistent between schema fields and rank profile inputs.
4. Check that fields referenced in fieldsets, rank profiles, and summaries exist in the document.
5. For deeper detail on types or advanced patterns, load these files from this skill's directory:
   - `docs/field-types.md` -- exhaustive type semantics, edge cases, storage characteristics.
   - `docs/schema-patterns.md` -- reusable patterns for multi-language, parent-child, time series, geo search.
