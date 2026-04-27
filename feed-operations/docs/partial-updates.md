# Partial Update Operations — Full Reference

Load this reference when writing partial `update` operations that go beyond a single `assign`. Covers every operator, tensor updates, upsert semantics, and idempotency.

## Operators

### assign

Replace the field value entirely.

```json
{ "update": "id:ns:type::key", "fields": { "title": { "assign": "New Title" } } }
```

Works on all field types. Assigning `null` clears the field.

### add (array / weightedset)

Append items to an array, or add entries to a weighted set.

```json
{
  "update": "id:ns:type::key",
  "fields": {
    "tags": { "add": ["rock", "alternative"] },
    "tokens": { "add": { "word1": 1, "word2": 3 } }
  }
}
```

### remove (array / weightedset)

Remove items from an array or entries from a weighted set.

```json
{
  "update": "id:ns:type::key",
  "fields": {
    "tags": { "remove": ["rock"] },
    "tokens": { "remove": { "word1": 0 } }
  }
}
```

For weighted sets, the weight value in the remove object is ignored; only the key matters.

### Arithmetic operators

These work on numeric fields (`int`, `long`, `float`, `double`).

| Operator | Description | Example |
|---|---|---|
| `increment` | Add a value | `{ "increment": 5 }` |
| `decrement` | Subtract a value | `{ "decrement": 2 }` |
| `multiply` | Multiply by a value | `{ "multiply": 1.5 }` |
| `divide` | Divide by a value | `{ "divide": 2.0 }` |

```json
{
  "update": "id:ns:type::key",
  "fields": {
    "play_count": { "increment": 1 },
    "score": { "multiply": 0.95 }
  }
}
```

### modify (tensor cells)

Update individual cells of a mapped or mixed tensor without replacing the whole tensor.

```json
{
  "update": "id:ns:type::key",
  "fields": {
    "embedding": {
      "modify": {
        "operation": "replace",
        "cells": [
          { "address": { "x": "label1" }, "value": 3.0 }
        ]
      }
    }
  }
}
```

Supported `operation` values: `replace`, `add`, `multiply`.

### create: true (upsert)

When `create` is set to `true` on an update, Vespa creates the document with default field values and then applies the update if the document does not already exist.

```json
{
  "update": "id:ns:type::key",
  "create": true,
  "fields": {
    "play_count": { "increment": 1 }
  }
}
```

Via the REST API, pass `?create=true` as a query parameter instead.

## Idempotency Notes

- **assign**: Idempotent. Applying the same assign twice yields the same result.
- **add (array)**: NOT idempotent. Repeated application appends duplicate entries.
- **add (weightedset)**: Idempotent. Re-adding the same key with the same weight is a no-op.
- **remove**: Idempotent. Removing an already-absent element is a no-op.
- **increment / decrement / multiply / divide**: NOT idempotent. Repeated application compounds the effect.
- **modify (tensor)**: Depends on the operation — `replace` is idempotent; `add` and `multiply` are not.
