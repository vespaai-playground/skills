---
name: "feed-operations"
description: "Vespa document CRUD operations and bulk feeding — covers document ID format, JSON wire format for put/update/remove, REST API endpoints, CLI commands, partial updates, conditional writes, bulk feeding, and document visiting/export."
---

# Vespa Feed Operations

## Overview

Vespa's feeding system is the pipeline through which documents enter, get updated in, and are removed from a content cluster. Every write travels through a **document processing chain** before being distributed to the appropriate content nodes via the distributor. The feeding layer supports individual CRUD operations as well as high-throughput bulk ingestion.

Key concepts:

- **Document**: a typed data record identified by a globally unique document ID.
- **Put**: insert or fully replace a document.
- **Update**: partially modify fields of an existing document.
- **Remove**: delete a document.
- **Feed client**: any component that submits document operations — the CLI, Java client, or raw HTTP calls.

## Document ID Format

Every document in Vespa is addressed by a **document ID** string with the following structure:

```
id:<namespace>:<document-type>::<user-specified-key>
```

| Component | Description |
|---|---|
| `id` | Fixed literal prefix. Always `id`. |
| `namespace` | Logical grouping; used together with document selection expressions and optionally for distribution. |
| `document-type` | Must match a `document` type declared in your schema. |
| `::` | Separator between the type and the user key. Note the double colon. |
| `user-specified-key` | Application-defined unique key. Can contain any character except newline. |

**Example:**

```
id:mynamespace:music::doc-1
```

### Group Modifiers

For grouped distribution (used with `storage` mode or streaming mode), insert a modifier between the document type and the user key:

- **String group:** `id:ns:type:g=<group-name>:<key>`
- **Numeric group:** `id:ns:type:n=<number>:<key>`

```
id:shop:order:g=customer_abc:order-789
id:shop:order:n=12345:order-790
```

The group modifier determines which distributor bucket the document maps to, ensuring all documents with the same group value are co-located on the same content node set.

## Document JSON Format

Each feed operation is expressed as a JSON object with an operation field and, where applicable, a `fields` object.

### PUT (insert or replace)

```json
{
  "put": "id:mynamespace:music::doc-1",
  "fields": {
    "artist": "Radiohead",
    "title": "OK Computer",
    "year": 1997
  }
}
```

A put **fully replaces** the document if it already exists.

### UPDATE (partial modification)

```json
{
  "update": "id:mynamespace:music::doc-1",
  "fields": {
    "year": { "assign": 1997 },
    "play_count": { "increment": 1 }
  }
}
```

Updates only touch the specified fields. See the "Partial Update Operations" section for the full set of update operators.

### REMOVE

```json
{
  "remove": "id:mynamespace:music::doc-1"
}
```

Removes require only the document ID. No `fields` object is needed.

## REST API Endpoints (`/document/v1`)

The document/v1 API is served by the container (gateway) nodes.

| HTTP Method | Path | Operation |
|---|---|---|
| `POST` | `/document/v1/{namespace}/{document-type}/docid/{user-key}` | Put (insert/replace) |
| `PUT` | `/document/v1/{namespace}/{document-type}/docid/{user-key}` | Update (partial) |
| `DELETE` | `/document/v1/{namespace}/{document-type}/docid/{user-key}` | Remove |
| `GET` | `/document/v1/{namespace}/{document-type}/docid/{user-key}` | Get (retrieve) |

For documents with group modifiers, use `group` or `number` path segments instead of `docid`:

```
POST /document/v1/shop/order/group/customer_abc/order-789
POST /document/v1/shop/order/number/12345/order-790
```

### Common Query Parameters

| Parameter | Description |
|---|---|
| `timeout` | Operation timeout, e.g. `5s`, `500ms`. Defaults to server config. |
| `route` | Override the document route, e.g. `default`. Rarely needed. |
| `condition` | Document selection expression for conditional writes. |
| `create` | Boolean. If `true`, an update creates the document if it does not exist (upsert). |
| `tracelevel` | Integer 1-9. Returns trace information for debugging feed pipelines. |

For curl examples of every HTTP method against `/document/v1`, load `docs/rest-api.md`.

## CLI Commands

The `vespa` CLI wraps the REST API for convenience.

### Single-document operations

```bash
# Put a document from a JSON file
vespa document put src/test/resources/doc.json

# Put with an explicit document ID (overrides any ID in the file)
vespa document put id:mynamespace:music::doc-1 src/test/resources/doc.json

# Get a document
vespa document get id:mynamespace:music::doc-1

# Remove a document
vespa document remove id:mynamespace:music::doc-1
```

### Bulk feeding

```bash
# Feed a JSONL file (one JSON operation per line)
vespa feed docs.jsonl

# With concurrency tuning
vespa feed --connections 4 --max-streams-per-connection 128 docs.jsonl

# Feed from stdin
cat docs.jsonl | vespa feed -

# Feed a directory of JSON/JSONL files
vespa feed my-feed-dir/
```

## Partial Update Operations

Every partial-update field wraps its value in an operator object. The core operator set:

| Operator | Applies to | Purpose |
|---|---|---|
| `assign` | all types | Replace entire value. Assigning `null` clears. |
| `add` | array, weightedset | Append/add entries. |
| `remove` | array, weightedset | Remove entries. |
| `increment`, `decrement`, `multiply`, `divide` | numeric | Arithmetic. |
| `modify` | mapped/mixed tensor | Update specific tensor cells (`operation`: replace/add/multiply). |

Set `"create": true` on an update (or `?create=true` on REST) for upsert semantics.

**Idempotency:** `assign`, `add (weightedset)`, `remove` are idempotent; `add (array)`, arithmetic operators, and `modify (add/multiply)` are NOT. Design retry logic accordingly.

For per-operator examples, full tensor-modify syntax, and detailed idempotency notes, load `docs/partial-updates.md`.

## Bulk Feeding

### JSONL Format

For bulk feeding, use JSONL (one JSON operation per line). Each line is a self-contained put, update, or remove:

```jsonl
{"put": "id:ns:music::1", "fields": {"artist": "Radiohead", "title": "OK Computer"}}
{"put": "id:ns:music::2", "fields": {"artist": "Björk", "title": "Homogenic"}}
{"update": "id:ns:music::1", "fields": {"play_count": {"increment": 1}}}
{"remove": "id:ns:music::3"}
```

You can also use a top-level JSON array, but JSONL is preferred for large files because it enables streaming without loading the entire file into memory.

### Client Hierarchy

Vespa provides multiple feed clients at different abstraction levels:

```
vespa feed CLI (highest level)
    └── vespa-feed-client (Java library)
            └── HTTP POST/PUT/DELETE to /document/v1 (lowest level)
```

- **`vespa feed` CLI**: Recommended for most use cases. Handles connection pooling, retry, throttling, and progress reporting.
- **`vespa-feed-client` (Java)**: A library for applications that need to embed feeding logic. Provides async API with completable futures.
- **HTTP `/document/v1`**: The raw REST endpoint. Use directly from any language with an HTTP client when the Java client is not an option.

### Performance Tuning

- **`--connections`**: Number of HTTP/2 connections to each container node. Default is typically 1. Increase for higher throughput if the container has CPU headroom.
- **`--max-streams-per-connection`**: Number of concurrent HTTP/2 streams per connection. Default 128. The product of connections x streams gives total concurrent in-flight operations.
- **Sizing**: A single `vespa feed` process with 4 connections and 128 streams (512 in-flight) can typically saturate a moderately sized cluster.
- **Batching**: The client automatically pipelines operations over HTTP/2 multiplexing. There is no explicit batch API — just feed as fast as you can and the client handles back-pressure.
- **Container thread pool**: Ensure the container has enough `<threads>` configured in `services.xml` to handle the feed concurrency.
- **Content node write throughput**: Monitor `content.proton.documentdb.feeding.commit.latency` to identify bottlenecks on content nodes.

## Conditional Writes

Use the `condition` field (JSON format) or `condition` query parameter (REST API) to make a write contingent on the current state of the document. The condition is a **document selection expression**.

### JSON format

```json
{
  "put": "id:ns:music::doc-1",
  "condition": "music.version == 3",
  "fields": {
    "artist": "Radiohead",
    "title": "OK Computer",
    "version": 4
  }
}
```

### REST API

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  --data '{"fields":{"artist":"Radiohead","version":4}}' \
  "http://localhost:8080/document/v1/ns/music/docid/doc-1?condition=music.version%3D%3D3"
```

If the condition evaluates to `false`, the operation returns a **412 Precondition Failed** response and the document is not modified.

Conditions reference field values using the syntax `<document-type>.<field-name>`. Complex expressions with `AND`, `OR`, `NOT`, comparisons, and regex are supported. Examples:

```
music.year > 2000 AND music.genre == "rock"
music.title =~ "^OK.*"
```

## Visit / Export

Use `vespa visit` (CLI) or `GET /document/v1/` with continuation tokens to iterate over documents. Supports selection expressions (`--selection "music.year > 2000"`) and field-set filtering.

For the full pagination pattern, CLI/REST parameter tables, and selection-expression syntax, load `docs/visiting-export.md`.

## Gotchas and Common Pitfalls

### Auto-expire with gc-selection

If your schema or `services.xml` defines a `gc-selection` (garbage collection selection), documents that do not match the expression will be **automatically removed** by background GC. This can surprise you if you update a field that is part of the GC selection and the document no longer matches.

```xml
<documents garbage-collection="true">
  <document type="music" selection="music.expiry_time > now() - 86400" />
</documents>
```

### Partial Update on Missing Document

By default, a partial update on a **non-existent document fails silently** — it returns success (200) but has no effect because there is nothing to update. To get upsert behavior, set `"create": true` in the JSON or `?create=true` on the REST API. This creates the document with schema-default field values before applying the update.

### Idempotency Differences Between Operations

- **Put** and **remove** are naturally idempotent.
- **Arithmetic updates** (`increment`, `decrement`, `multiply`, `divide`) and **array `add`** are NOT idempotent. If your feed pipeline may retry, consider using conditional writes or `assign` instead.
- In failure/retry scenarios, non-idempotent operations can cause data drift. Design your pipeline accordingly.

### Tensor Update Syntax

Tensor fields require specific JSON syntax that differs from scalar fields. Common mistakes:

- Using `assign` with a tensor requires the full tensor cell format:
  ```json
  { "assign": { "cells": [{"address":{"x":"0","y":"0"}, "value":1.0}] } }
  ```
  or the short form for dense tensors:
  ```json
  { "assign": [1.0, 2.0, 3.0] }
  ```
- `modify` only works on mapped and mixed tensors. It cannot be used on purely indexed (dense) tensors.
- When using `modify`, the `operation` field is required (`replace`, `add`, or `multiply`).

### Test-and-Set Ordering

Conditional writes (test-and-set) are evaluated on the **content node** that owns the document. If two conditional writes race, only one will succeed. There is no global ordering guarantee across different documents.

### Route and Distribution

Feeding operations are routed through the **distributor** on content nodes. The distributor determines the correct bucket and replica set. Under normal conditions you should not override the `route` parameter. Misconfigured routes can cause documents to be silently dropped.

> **For deeper detail**, load `docs/partial-updates.md`, `docs/visiting-export.md`, `docs/rest-api.md`, `docs/document-json.md`, or `docs/feed-clients.md` from this skill's directory as needed.
