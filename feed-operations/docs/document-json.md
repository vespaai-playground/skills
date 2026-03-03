# Vespa Document JSON Reference

Complete reference for the JSON format used in Vespa feed operations.

## Document ID Format

All operations reference a document by its full document ID:

```
id:{namespace}:{document-type}::{user-specific-key}
```

With optional group or number modifier:

```
id:{namespace}:{document-type}:g={group}:{key}
id:{namespace}:{document-type}:n={number}:{key}
```

Examples:

```
id:mynamespace:music::doc-1
id:mynamespace:music:g=user123:doc-1
id:mynamespace:music:n=12345:doc-1
```

---

## Put Operation

Creates or fully replaces a document.

```json
{
  "put": "id:mynamespace:music::doc-1",
  "fields": {
    "title": "Example Song",
    "artist": "Example Artist",
    "year": 2024,
    "tags": ["rock", "alternative"],
    "rating": 4.5,
    "embedding": { "values": [0.1, 0.2, 0.3, 0.4] }
  }
}
```

All fields declared in the schema can be included. Fields not included are set to their default values. A put to an existing document ID fully replaces the previous document.

---

## Update Operation

Partially modifies an existing document. Only specified fields are changed.

```json
{
  "update": "id:mynamespace:music::doc-1",
  "fields": {
    "title": { "assign": "New Title" }
  }
}
```

### Update Operators

#### assign

Replaces the entire field value. Works on all field types.

```json
{
  "update": "id:mynamespace:music::doc-1",
  "fields": {
    "title": { "assign": "New Title" },
    "year": { "assign": 2025 },
    "tags": { "assign": ["pop", "electronic"] },
    "rating": { "assign": null }
  }
}
```

Assigning `null` clears the field.

#### add (array)

Appends elements to an array field.

```json
{
  "update": "id:mynamespace:music::doc-1",
  "fields": {
    "tags": { "add": ["new_tag", "another_tag"] }
  }
}
```

#### add (weighted set)

Adds entries to a weighted set. Values are the weights.

```json
{
  "update": "id:mynamespace:music::doc-1",
  "fields": {
    "genre_weights": { "add": { "rock": 10, "pop": 5 } }
  }
}
```

If the key already exists, its weight is updated.

#### remove (array)

Removes matching elements from an array field.

```json
{
  "update": "id:mynamespace:music::doc-1",
  "fields": {
    "tags": { "remove": ["old_tag"] }
  }
}
```

#### remove (weighted set)

Removes entries from a weighted set. The values in the map are ignored (convention is 0).

```json
{
  "update": "id:mynamespace:music::doc-1",
  "fields": {
    "genre_weights": { "remove": { "rock": 0 } }
  }
}
```

#### increment

Increases a numeric field value.

```json
{
  "update": "id:mynamespace:music::doc-1",
  "fields": {
    "play_count": { "increment": 1 }
  }
}
```

#### decrement

Decreases a numeric field value.

```json
{
  "update": "id:mynamespace:music::doc-1",
  "fields": {
    "play_count": { "decrement": 1 }
  }
}
```

#### multiply

Multiplies a numeric field value.

```json
{
  "update": "id:mynamespace:music::doc-1",
  "fields": {
    "rating": { "multiply": 2 }
  }
}
```

#### divide

Divides a numeric field value.

```json
{
  "update": "id:mynamespace:music::doc-1",
  "fields": {
    "rating": { "divide": 2 }
  }
}
```

#### match (map and struct updates)

Updates a specific entry within a map or a specific field within a struct, without replacing the entire structure.

Map example:

```json
{
  "update": "id:mynamespace:music::doc-1",
  "fields": {
    "metadata{\"source\"}": { "assign": "spotify" }
  }
}
```

Struct field example:

```json
{
  "update": "id:mynamespace:music::doc-1",
  "fields": {
    "address.city": { "assign": "Oslo" }
  }
}
```

#### modify (tensor)

Modifies individual tensor cells. Supports `replace`, `add`, and `multiply` operations.

```json
{
  "update": "id:mynamespace:music::doc-1",
  "fields": {
    "embedding": {
      "modify": {
        "operation": "replace",
        "cells": [
          { "address": { "x": "0" }, "value": 0.99 },
          { "address": { "x": "1" }, "value": 0.88 }
        ]
      }
    }
  }
}
```

Other tensor modify operations:

```json
{ "modify": { "operation": "add", "cells": [...] } }
{ "modify": { "operation": "multiply", "cells": [...] } }
```

---

## Remove Operation

Deletes a document by ID.

```json
{
  "remove": "id:mynamespace:music::doc-1"
}
```

No `fields` are needed. If the document does not exist, the operation is a no-op (no error).

---

## Tensor Value Formats

### Short Form (indexed tensors)

For dense, indexed tensors. Values are listed in dimension order.

```json
{
  "embedding": { "values": [0.1, 0.2, 0.3, 0.4, 0.5] }
}
```

This is the most compact form and is preferred for indexed tensors such as `tensor<float>(x[5])`.

### Cell Format

Explicit address-value pairs. Works for all tensor types.

```json
{
  "embedding": {
    "cells": [
      { "address": { "x": "0" }, "value": 0.1 },
      { "address": { "x": "1" }, "value": 0.2 },
      { "address": { "x": "2" }, "value": 0.3 }
    ]
  }
}
```

For mapped tensors like `tensor<float>(category{})`:

```json
{
  "weights": {
    "cells": [
      { "address": { "category": "sports" }, "value": 0.8 },
      { "address": { "category": "news" }, "value": 0.2 }
    ]
  }
}
```

### Block Format (mixed tensors)

For mixed tensors that have both mapped and indexed dimensions, such as `tensor<float>(category{}, x[3])`.

```json
{
  "mixed_embedding": {
    "blocks": {
      "sports": [0.1, 0.2, 0.3],
      "news": [0.4, 0.5, 0.6]
    }
  }
}
```

Block format can also be expressed as an array:

```json
{
  "mixed_embedding": {
    "blocks": [
      { "address": { "category": "sports" }, "values": [0.1, 0.2, 0.3] },
      { "address": { "category": "news" }, "values": [0.4, 0.5, 0.6] }
    ]
  }
}
```

---

## Create (Upsert on Update)

By default, an update to a non-existent document returns an error. Set `"create": true` to auto-create the document if it does not exist. Field values not specified in the update use schema defaults.

```json
{
  "update": "id:mynamespace:music::doc-1",
  "create": true,
  "fields": {
    "play_count": { "increment": 1 }
  }
}
```

This is commonly used for counters, accumulators, and upsert patterns.

---

## Conditional Writes (Test-and-Set)

The `condition` field applies a test-and-set condition. The operation only executes if the condition evaluates to true against the existing document. If the condition fails, the operation returns HTTP 412 Precondition Failed.

```json
{
  "update": "id:mynamespace:music::doc-1",
  "condition": "music.year == 2024",
  "fields": {
    "year": { "assign": 2025 }
  }
}
```

Conditions support comparison operators, logical operators, and field access:

```json
{ "condition": "music.rating > 3.0" }
{ "condition": "music.title == \"Old Title\"" }
{ "condition": "music.year >= 2020 AND music.rating > 4.0" }
```

Conditions work with put, update, and remove operations.

---

## Fieldpath Updates for Struct and Map Fields

Fieldpath syntax allows targeted updates to nested structures without the `match` operator.

### Map field updates

```json
{
  "update": "id:mynamespace:music::doc-1",
  "fields": {
    "metadata{\"source\"}": { "assign": "spotify" },
    "metadata{\"imported\"}": { "assign": "true" }
  }
}
```

### Struct field updates

```json
{
  "update": "id:mynamespace:music::doc-1",
  "fields": {
    "artist_info.name": { "assign": "New Name" },
    "artist_info.country": { "assign": "Norway" }
  }
}
```

### Nested map within struct

```json
{
  "update": "id:mynamespace:music::doc-1",
  "fields": {
    "artist_info.social_links{\"twitter\"}": { "assign": "@example" }
  }
}
```

---

## Feed Formats

### JSONL Format (recommended for bulk feeding)

One JSON operation per line. No separating commas. This is the preferred format for `vespa feed`.

```jsonl
{"put": "id:ns:music::1", "fields": {"title": "Song One", "year": 2024}}
{"put": "id:ns:music::2", "fields": {"title": "Song Two", "year": 2023}}
{"update": "id:ns:music::3", "fields": {"year": {"assign": 2025}}}
{"remove": "id:ns:music::4"}
```

### Batch Array Format

A JSON array of operations. Accepted by the `/document/v1` batch endpoint and `vespa feed`.

```json
[
  {"put": "id:ns:music::1", "fields": {"title": "Song One"}},
  {"put": "id:ns:music::2", "fields": {"title": "Song Two"}},
  {"remove": "id:ns:music::3"}
]
```

---

## Common JSON Mistakes and Fixes

**Mistake: Using `"id"` instead of `"put"` / `"update"` / `"remove"`**

```json
// WRONG
{"id": "id:ns:type::1", "fields": {"title": "Test"}}

// CORRECT
{"put": "id:ns:type::1", "fields": {"title": "Test"}}
```

**Mistake: Missing the operation wrapper on update fields**

```json
// WRONG - assigns literally, does not use operator
{"update": "id:ns:type::1", "fields": {"count": 5}}

// CORRECT - uses the assign operator
{"update": "id:ns:type::1", "fields": {"count": {"assign": 5}}}
```

**Mistake: Incorrect document ID format**

```json
// WRONG - missing double colon before key
{"put": "id:ns:type:1", "fields": {}}

// CORRECT
{"put": "id:ns:type::1", "fields": {}}
```

**Mistake: Using flat array for tensor instead of values wrapper**

```json
// WRONG
{"put": "id:ns:type::1", "fields": {"embedding": [0.1, 0.2, 0.3]}}

// CORRECT
{"put": "id:ns:type::1", "fields": {"embedding": {"values": [0.1, 0.2, 0.3]}}}
```

**Mistake: Trailing comma in JSONL**

```jsonl
// WRONG - JSONL lines must not have trailing commas
{"put": "id:ns:type::1", "fields": {"title": "A"}},
{"put": "id:ns:type::2", "fields": {"title": "B"}},

// CORRECT
{"put": "id:ns:type::1", "fields": {"title": "A"}}
{"put": "id:ns:type::2", "fields": {"title": "B"}}
```

**Mistake: Wrapping JSONL in an array**

```json
// WRONG for JSONL format (this is batch array format)
[{"put": "id:ns:type::1", "fields": {"title": "A"}}]

// CORRECT JSONL (no array wrapper, one object per line)
{"put": "id:ns:type::1", "fields": {"title": "A"}}
```

**Mistake: Using `create` with put operations**

```json
// WRONG - create only applies to update
{"put": "id:ns:type::1", "create": true, "fields": {"title": "A"}}

// CORRECT - put always creates/replaces, no create flag needed
{"put": "id:ns:type::1", "fields": {"title": "A"}}

// create is for update (upsert)
{"update": "id:ns:type::1", "create": true, "fields": {"count": {"increment": 1}}}
```
