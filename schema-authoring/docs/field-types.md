# Vespa Field Type Reference

Complete reference for all Vespa field types, their indexing directives, constraints, and common pitfalls.

## Field Type Matrix

| Type | Description | Can Index | Can Attribute | Can Summary | Notes |
|------|-------------|-----------|---------------|-------------|-------|
| `string` | UTF-8 text | Yes (tokenized) | Yes (exact match) | Yes | Most versatile type; behavior differs drastically between index and attribute mode |
| `int` | 32-bit signed integer | Yes | Yes | Yes | Range: -2^31 to 2^31-1 |
| `long` | 64-bit signed integer | Yes | Yes | Yes | Range: -2^63 to 2^63-1; use for timestamps, large IDs |
| `byte` | 8-bit signed integer | No | Yes | Yes | Range: -128 to 127; compact storage for small values |
| `float` | 32-bit IEEE 754 | Yes | Yes | Yes | ~7 decimal digits of precision |
| `double` | 64-bit IEEE 754 | Yes | Yes | Yes | ~15 decimal digits of precision |
| `bool` | Boolean true/false | No | Yes | Yes | Stored as single bit in attributes; cannot be used as index |
| `position` | Geo coordinate | No | Yes | Yes | Format: `N37.416383;W122.024683`; enables geo-distance ranking |
| `uri` | URI/URL | Yes | Yes | Yes | Tokenized by URI components (host, path, etc.) when indexed |
| `predicate` | Boolean predicate expression | Yes | No | No | For boolean constraint matching; uses special predicate index |
| `raw` | Arbitrary binary data | No | No | Yes | Opaque byte sequence; no search or filtering |
| `reference<doc_type>` | Reference to parent document | No | Yes (always) | No | Enables parent-child joins via `import field` |
| `tensor<vt>(dims)` | Multi-dimensional numeric data | Yes (HNSW ANN) | Yes | Yes | Primary type for vectors and ML features |
| `array<T>` | Ordered collection of T | Inherits from T | Inherits from T | Yes | No size limit enforced at schema level |
| `weightedset<T>` | Set of T with integer weights | Inherits from T | Inherits from T | Yes | T must be `string` or `long`/`int` |
| `map<K,V>` | Key-value pairs | No | No (use struct-field) | Yes | Syntactic sugar for `array<struct>` with `key` and `value` fields |

## String Indexing Modes

String fields behave very differently depending on their indexing directives.

### Index Mode (Tokenized Full-Text Search)

```sd
field title type string {
    indexing: index | summary
    index: enable-bm25
    match: text           # default for indexed strings
    stemming: best        # default stemmer
}
```

- Text is tokenized, normalized, and stemmed
- Supports `contains`, `phrase`, `near`, `onear`, `equiv`, and `weakAnd` query operators
- Supports BM25 and nativeRank relevance features
- Cannot be used for sorting or grouping
- Linguistic processing (stemming, normalization) is applied

### Attribute Mode (Exact Match, Sort, Group)

```sd
field category type string {
    indexing: attribute | summary
    attribute: fast-search  # optional: builds B-tree index for fast equality/prefix
    match: exact             # default for attribute strings
    rank: filter             # optional: mark as filter to save rank resources
}
```

- Stored unprocessed in memory (column store)
- Supports `=` (exact match), sorting, grouping, and range queries (prefix with `fast-search`)
- No tokenization, stemming, or linguistic processing
- Consumes memory proportional to corpus size
- Add `fast-search` for large-cardinality fields that need equality lookups

### Both Index and Attribute

```sd
field title type string {
    indexing: index | attribute | summary
}
```

- Full-text search via index, plus sorting/grouping via attribute
- Doubles storage: disk-based index + in-memory attribute
- Use only when you genuinely need both text search and sort/group on the same field

## Numeric Types: Precision and Use Cases

| Type | Bits | Range | Typical Use |
|------|------|-------|-------------|
| `byte` | 8 | -128 to 127 | Compact flags, small enums |
| `int` | 32 | -2,147,483,648 to 2,147,483,647 | Counts, categorical IDs |
| `long` | 64 | -9.2 x 10^18 to 9.2 x 10^18 | Timestamps (epoch millis), large IDs |
| `float` | 32 | ~7 significant digits | Scores, coordinates when precision is acceptable |
| `double` | 64 | ~15 significant digits | High-precision scores, monetary values |

All numeric types can be `attribute` (in-memory for sorting/grouping/filtering) and `index` (for fast matching). Numeric index is a B-tree, not an inverted index.

```sd
field timestamp type long {
    indexing: attribute | summary
    attribute: fast-search   # B-tree for fast range queries
}
```

## Tensor Type Syntax

Tensors are Vespa's type for vectors, matrices, and higher-order numeric data. The full syntax is:

```
tensor<value-type>(dimension-spec, ...)
```

### Value Types

| Value Type | Bits | Use Case |
|------------|------|----------|
| `float` | 32 | Default for embeddings; good balance of precision and size |
| `double` | 64 | High precision ML features; rare for embeddings |
| `int8` | 8 | Quantized embeddings; binary vectors; 4x memory savings over float |
| `bfloat16` | 16 | Reduced precision embeddings; 2x memory savings over float |

### Dimension Types

**Indexed (dense) dimension** -- fixed-size, square-bracket syntax:

```sd
field embedding type tensor<float>(x[384]) {
    indexing: attribute | index | summary
    attribute {
        distance-metric: angular    # or euclidean, dotproduct, prenormalized-angular, hamming
    }
    index {
        hnsw {
            max-links-per-node: 16
            neighbors-to-explore-at-insert: 200
        }
    }
}
```

**Mapped (sparse) dimension** -- variable-size, curly-brace syntax:

```sd
field user_features type tensor<float>(feature{}) {
    indexing: attribute | summary
}
```

Mapped dimensions act like labeled dictionaries. The label is a string key. These cannot use HNSW index.

**Mixed dimensions** -- combine mapped and indexed:

```sd
field per_category_embedding type tensor<float>(category{}, x[128]) {
    indexing: attribute | summary
}
```

Mixed tensors store one dense sub-tensor per mapped label. Useful for multi-vector representations (e.g., ColBERT) or per-category embeddings.

### Tensor Indexing Rules

- `attribute`: Required for all tensors. Stores tensor data in memory.
- `index`: Only valid for tensors with exactly one indexed dimension (pure dense vectors). Enables HNSW approximate nearest neighbor search.
- `summary`: Optional. Include tensor in document summaries / result output.
- Mixed and mapped tensors cannot use `index` (no HNSW). Use brute-force `nearestNeighbor` or `closeness` with attribute only.

## Collection Types

### array<T>

Ordered, variable-length list of elements of type T.

```sd
field tags type array<string> {
    indexing: index | summary       # each element is tokenized and indexed
}

field scores type array<float> {
    indexing: attribute | summary    # in-memory array attribute
}
```

- Matching semantics: a query matches if any element in the array matches.
- When used as attribute, the full array is in memory.
- No built-in size limit at schema level (control in application logic or via document processor).

### weightedset<T>

Set of unique values of type T, each with an associated integer weight.

```sd
field categories type weightedset<string> {
    indexing: attribute | summary
    weightedset {
        create-if-nonexistent    # auto-create entry with weight 0 on partial update
        remove-if-zero           # remove entry when weight reaches 0
    }
}
```

- T must be `string`, `int`, or `long`.
- Weights are surfaced via `rawScore` and `itemRawScore` rank features.
- `create-if-nonexistent`: On a `partial update` that increments/decrements, creates the key with weight 0 if it does not exist before applying the operation.
- `remove-if-zero`: Automatically removes the entry if its weight becomes 0 after an update.

### map<K,V>

Key-value collection. Internally represented as `array<struct<key K, value V>>`.

```sd
field metadata type map<string, string> {
    indexing: summary
    struct-field key   { indexing: attribute }
    struct-field value { indexing: attribute }
}
```

- You cannot directly `index` or `attribute` a map field itself; you must declare `struct-field` directives on `key` and `value` individually.
- Filtering on map key/value requires the struct-field sub-declarations.

## Position Type

Geo-location field using Vespa's coordinate format.

```sd
field location type position {
    indexing: attribute | summary
}
```

- Feed format: `N37.416383;W122.024683` (latitude N/S, longitude E/W, in degrees)
- Alternative JSON feed format: `{"lat": 37.416383, "lng": -122.024683}`
- Enables `closeness(field, location)` and `distance(field, location)` rank features
- Use with `geoLocation` query filter for bounding-box or radius filtering
- Always stored as attribute (in-memory); cannot be an index-only field

## Reference Type

Establishes a parent-child relationship between document types.

```sd
schema child_doc {
    document child_doc {
        field parent_ref type reference<parent_doc> {
            indexing: attribute | summary
        }
    }
    import field parent_ref.parent_field as local_alias {}
}
```

- The referenced parent document type must be declared as `global` in services.xml.
- `reference` fields must always be `attribute` (they are looked up in memory).
- Use `import field` at schema level (outside `document {}`) to project parent fields into the child.
- Imported fields behave as if they are native attribute fields on the child (can filter, sort, group, rank).
- Cannot be used as `index`.
- Cannot be inside a struct or collection type.

## Predicate Type

For boolean constraint matching (e.g., ad targeting).

```sd
field targeting type predicate {
    indexing: attribute | index
    index {
        arity: 2                # required: controls interval algorithm resolution
        lower-bound: 0          # optional: hint for range features
        upper-bound: 1000       # optional: hint for range features
    }
}
```

- Stores boolean expressions like `gender in ['male'] and age in [20..30]`.
- Queried with `predicate(targeting, {"gender": "male"}, {"age": 25L})`.
- Must have both `attribute` and `index`.
- Cannot be used as `summary`.

## Common Mistakes by Type

| Type | Mistake | Fix |
|------|---------|-----|
| `string` | Using `attribute` and expecting tokenized text search | Use `index` for text search; `attribute` gives exact match only |
| `string` | Sorting on an `index`-only string field | Add `attribute` to enable sorting |
| `int`/`long` | Using `index` instead of `attribute` for filter/sort | Prefer `attribute` with `fast-search` for numeric filtering |
| `tensor` | Adding `index` to a mapped or mixed tensor | HNSW index only works with a single indexed (dense) dimension |
| `tensor` | Omitting `distance-metric` on an ANN field | Default is `euclidean`; set explicitly to match your embedding model |
| `bool` | Trying to add `index` to a bool | Bool only supports `attribute` mode |
| `position` | Feeding coordinates as plain floats | Use `N37.4;W122.0` format or JSON `{"lat":..,"lng":..}` |
| `reference` | Forgetting to mark parent as `global: true` in services.xml | Parent documents in references must be global |
| `map` | Expecting direct filtering on map fields | Declare `struct-field` on key/value with `attribute` to enable filtering |
| `weightedset` | Using `float` as the element type | Only `string`, `int`, and `long` are supported as weightedset element types |
| `predicate` | Omitting the `arity` parameter in index block | `arity` is required for predicate fields |
| `array<string>` | Expecting per-element match info by default | Use `sameElement` operator or array-of-struct for correlated matching |
