---
name: "pyvespa"
description: "Python API for Vespa.ai — define schemas, deploy applications, feed documents, query, and manage Vespa from Python using pyvespa."
---

# pyvespa Skill

Use this skill when the user is working with Vespa from Python — defining application packages programmatically, deploying to Docker or Vespa Cloud, feeding documents, querying, or using the query builder DSL.

> **Deeper references** — load `docs/package-api.md` for the full configuration class reference (Schema, Field, RankProfile, etc.) and `docs/application-api.md` for the Vespa connection, feed, query, and deployment APIs.

## Overview

**pyvespa** is the official Python client for Vespa.ai. Install with:

```bash
pip install pyvespa
```

Requires Python >=3.10, <3.14. Zero native dependencies for querying/feeding; Docker SDK needed only for local deployment.

### Core Modules

| Module | Purpose |
|--------|---------|
| `vespa.package` | Define application packages programmatically (schemas, fields, rank profiles, etc.) |
| `vespa.deployment` | Deploy to Docker (`VespaDocker`) or Vespa Cloud (`VespaCloud`) |
| `vespa.application` | Connect to a running Vespa instance — query, feed, get, update, delete, visit |
| `vespa.querybuilder` | Pythonic DSL for building YQL queries |

---

## Quick Start

```python
from vespa.package import (
    ApplicationPackage, Schema, Document, Field, FieldSet,
    RankProfile, HNSW, FirstPhaseRanking,
)
from vespa.deployment import VespaDocker

# 1. Define the application
app_package = ApplicationPackage(name="myapp")

app_package.schema.add_fields(
    Field(name="title", type="string",
          indexing=["index", "summary"], index="enable-bm25"),
    Field(name="body", type="string",
          indexing=["index", "summary"], index="enable-bm25"),
    Field(name="embedding", type="tensor<float>(x[384])",
          indexing=["index", "attribute"],
          ann=HNSW(distance_metric="angular")),
)
app_package.schema.add_field_set(FieldSet(name="default", fields=["title", "body"]))
app_package.schema.add_rank_profile(
    RankProfile(name="hybrid",
                inputs=[("query(q)", "tensor<float>(x[384])")],
                first_phase="bm25(title) + bm25(body) + closeness(field, embedding)",
                match_features=["bm25(title)", "bm25(body)", "closeness(field, embedding)"]),
)

# 2. Deploy locally
vespa_docker = VespaDocker(port=8080)
app = vespa_docker.deploy(app_package)

# 3. Feed a document
app.feed_data_point(
    schema="myapp",
    data_id="doc-1",
    fields={"title": "Vespa intro", "body": "Vespa is a serving engine", "embedding": [0.1] * 384},
)

# 4. Query
with app.syncio() as sess:
    response = sess.query(body={
        "yql": "select * from sources * where userQuery() or ({targetHits:10}nearestNeighbor(embedding, q))",
        "query": "serving engine",
        "ranking": "hybrid",
        "input.query(q)": [0.1] * 384,
    })
    for hit in response.hits:
        print(hit["fields"]["title"], hit["relevance"])
```

---

## ApplicationPackage

```python
ApplicationPackage(
    name: str,                              # Lowercase, [a-z0-9], starts with letter, max 20 chars
    schema: Optional[List[Schema]] = None,  # Defaults to one Schema matching name
    stateless_model_evaluation: bool = False,
    components: Optional[List[Component]] = None,
    auth_clients: Optional[List[AuthClient]] = None,
)
```

When created with defaults, an `ApplicationPackage` auto-creates a single `Schema` and `Document` with the same name. Access via `app_package.schema`.

**Key methods:**
- `app_package.schema` — returns the single schema (asserts exactly one)
- `app_package.get_schema(name)` — get a schema by name
- `app_package.add_schema(schema)` — add additional schemas
- `app_package.to_files(root)` — write to disk as a standard Vespa application directory
- `app_package.to_zip()` — serialize to a deployable zip (BytesIO)

### Multiple Schemas

```python
from vespa.package import Schema, Document

schema_a = Schema(name="article", document=Document())
schema_b = Schema(name="comment", document=Document())

app_package = ApplicationPackage(
    name="myapp",
    schema=[schema_a, schema_b],
    create_schema_by_default=False,
)
```

---

## Field

The most important configuration class.

```python
Field(
    name: str,
    type: str,                  # "string", "int", "long", "float", "double", "bool",
                                # "tensor<float>(x[384])", "array<string>", "weightedset<string>", etc.
    indexing: list | tuple | str,  # ["index", "summary"] → pipe-separated; tuple → multiline block
    index: str | dict = None,     # "enable-bm25", or dict for predicate arity etc.
    attribute: list = None,       # ["fast-search", "paged"]
    ann: HNSW = None,             # For tensor fields with ANN index
    match: list = None,           # [("exact", None)] or ["word"]
    bolding: True = None,
    summary: Summary = None,
    rank: str = None,             # "filter" for filter-only fields
    struct_fields: list = None,
)
```

**Indexing directive formats:**
- `["index", "summary"]` → `indexing: index | summary`
- `("input title | index | summary",)` → multiline `indexing { ... }` block (used for embed expressions)

**Common field patterns:**

```python
# Text field with BM25
Field(name="title", type="string", indexing=["index", "summary"], index="enable-bm25")

# Attribute for filtering/sorting
Field(name="price", type="float", indexing=["attribute", "summary"])

# Fast-search attribute
Field(name="category", type="string", indexing=["attribute", "summary"],
      attribute=["fast-search"])

# Tensor with HNSW
Field(name="embedding", type="tensor<float>(x[384])",
      indexing=["index", "attribute"],
      ann=HNSW(distance_metric="angular", max_links_per_node=16,
               neighbors_to_explore_at_insert=200))

# Embedder integration (multiline indexing)
Field(name="embedding", type="tensor<float>(x[384])",
      indexing=("input title . \" \" . input body | embed e5 | index | attribute",),
      ann=HNSW(distance_metric="angular"))

# Array field
Field(name="tags", type="array<string>", indexing=["attribute", "summary"])

# Weighted set
Field(name="labels", type="weightedset<string>", indexing=["attribute", "summary"])

# Filter-only field
Field(name="internal_id", type="long", indexing=["attribute"], rank="filter")
```

---

## HNSW

```python
HNSW(
    distance_metric: str = "euclidean",  # euclidean|angular|dotproduct|prenormalized-angular|hamming|geodegrees
    max_links_per_node: int = 16,
    neighbors_to_explore_at_insert: int = 200,
)
```

Use `angular` or `prenormalized-angular` for cosine similarity. Use `dotproduct` for maximum inner product.

---

## RankProfile

```python
RankProfile(
    name: str,
    first_phase: str | FirstPhaseRanking = None,
    second_phase: SecondPhaseRanking = None,
    global_phase: GlobalPhaseRanking = None,
    inherits: str = None,
    inputs: list = None,           # [("query(q)", "tensor<float>(x[384])")]
    functions: list = None,        # [Function(name, expression)]
    constants: dict = None,
    summary_features: list = None,
    match_features: list = None,
)
```

**Ranking phases:**

```python
from vespa.package import (
    RankProfile, FirstPhaseRanking, SecondPhaseRanking,
    GlobalPhaseRanking, Function,
)

RankProfile(
    name="hybrid",
    inputs=[("query(q)", "tensor<float>(x[384])")],
    functions=[
        Function(name="text_score", expression="bm25(title) + 0.5 * bm25(body)"),
        Function(name="vector_score", expression="closeness(field, embedding)"),
    ],
    first_phase=FirstPhaseRanking(expression="text_score + vector_score", keep_rank_count=1000),
    second_phase=SecondPhaseRanking(expression="text_score * 0.4 + vector_score * 0.6", rerank_count=100),
    match_features=["bm25(title)", "bm25(body)", "closeness(field, embedding)"],
)
```

---

## Deployment

### Local Docker

```python
from vespa.deployment import VespaDocker

vespa_docker = VespaDocker(port=8080)
app = vespa_docker.deploy(app_package)      # Returns Vespa instance

# Reconnect to existing container
vespa_docker = VespaDocker.from_container_name_or_id("vespa-container-name")
```

Docker needs at least **4 GB memory** allocated.

### Vespa Cloud

```python
from vespa.deployment import VespaCloud

vespa_cloud = VespaCloud(
    tenant="my-tenant",
    application="my-app",
    application_package=app_package,
    auth_client_token_id="my-token-id",   # For token-based data plane auth
)

# Deploy to dev
app = vespa_cloud.deploy()

# Or connect to existing deployment
app = vespa_cloud.get_application(endpoint_type="token")
```

**Auth modes:**
- **Control plane**: API key file via `key_location` or `key_content` param
- **Data plane (mTLS)**: auto-generated cert, or provide via `Vespa(cert=..., key=...)`
- **Data plane (token)**: set `auth_client_token_id` + `vespa_cloud_secret_token` env var

---

## Feeding Documents

### Single Document

```python
with app.syncio() as sess:
    response = sess.feed_data_point(
        schema="myschema",
        data_id="doc-1",
        fields={"title": "Hello", "count": 42},
    )
    assert response.is_successful()
```

### Bulk Feed

```python
docs = [{"id": str(i), "fields": {"title": f"Doc {i}"}} for i in range(10000)]

def callback(response, doc_id):
    if not response.is_successful():
        print(f"Failed: {doc_id} — {response.status_code}")

# Sync (thread pool)
app.feed_iterable(docs, schema="myschema", callback=callback, max_workers=8)

# Async (HTTP/2, preferred for throughput)
app.feed_async_iterable(docs, schema="myschema", callback=callback, max_workers=64)
```

**Feed data format** — each dict must have `"id"` (str) and `"fields"` (dict). Optional `"groupname"`.

### Update and Delete

```python
with app.syncio() as sess:
    # Partial update
    sess.update_data(schema="myschema", data_id="doc-1",
                     fields={"count": {"increment": 1}}, create=True)

    # Delete
    sess.delete_data(schema="myschema", data_id="doc-1")

# Bulk update/delete
app.feed_iterable(docs, schema="myschema", operation_type="update")
app.feed_iterable(ids, schema="myschema", operation_type="delete")
```

---

## Querying

### Direct Query

```python
with app.syncio() as sess:
    response = sess.query(body={
        "yql": "select * from sources * where title contains 'vespa'",
        "ranking": "bm25",
        "hits": 10,
    })
    print(response.hits)                        # List of hit dicts
    print(response.number_documents_retrieved)   # Total matches
```

### Batch Queries

```python
queries = [
    {"yql": "select * from sources * where title contains 'vespa'", "hits": 5},
    {"yql": "select * from sources * where title contains 'search'", "hits": 5},
]
responses = app.query_many(queries, num_connections=4, max_concurrent=100)
```

### Query Builder DSL

```python
import vespa.querybuilder as qb

title = qb.QueryField("title")
body = qb.QueryField("body")

# Text search
q = qb.select("*").from_("myschema").where(title.contains("vespa"))

# Boolean conditions
q = qb.select("*").from_("myschema").where(
    qb.all(title.contains("vespa"), body.contains("search"))
)

# Nearest neighbor
q = qb.select("*").from_("myschema").where(
    qb.nearestNeighbor("embedding", "q", annotations={"targetHits": 100})
)

# Hybrid: text + vector with rank()
q = qb.select("*").from_("myschema").where(
    qb.rank(
        qb.any(title.contains("vespa"), qb.nearestNeighbor("embedding", "q", annotations={"targetHits": 100})),
        title.contains("vespa"),
    )
)

# weakAnd
q = qb.select("*").from_("myschema").where(
    qb.weakAnd(title.contains("big"), title.contains("data"), annotations={"targetHits": 200})
)

# Pagination and ordering
q = q.set_limit(10).set_offset(20).order_by("price", ascending=True)

# Add query parameters
q = q.param("ranking", "hybrid").param("input.query(q)", [0.1] * 384)

# Build YQL string
yql = str(q)
```

### Grouping

```python
from vespa.querybuilder import Grouping as G

grouping = G.all(
    G.group("category"),
    G.each(G.output(G.count(), G.avg("price")))
)
q = qb.select("*").from_("myschema").where(title.contains("vespa")).groupby(str(grouping))
```

---

## Visit (Export All Documents)

```python
for slice_ in app.visit(schema="myschema", content_cluster_name="content", slices=4):
    for response in slice_:
        for doc in response.documents:
            print(doc["id"], doc["fields"])
```

---

## Gotchas

1. **App name restrictions** — `ApplicationPackage(name=...)` must be lowercase `[a-z0-9]`, start with letter, max 20 chars. No hyphens or underscores.
2. **Tuple vs list for indexing** — use a tuple `("input title | embed e5 | index",)` for multiline/embed expressions; use a list `["index", "summary"]` for pipe-separated.
3. **Namespace defaults to schema name** — if you don't pass `namespace` to feed/query methods, it defaults to the `schema` parameter value.
4. **Docker memory** — allocate at least 4 GB to Docker for local deployments.
5. **`feed_async_iterable` vs `feed_iterable`** — async is better for throughput (HTTP/2 multiplexing over 1 connection); sync uses a thread pool with multiple connections.
6. **Context managers** — always use `app.syncio()` or `app.asyncio()` for production code to manage connections properly.
7. **`is_successful()`** — use this (not the deprecated misspelled `is_successfull()`).
8. **Cloud token auth** — set `VESPA_CLOUD_SECRET_TOKEN` env var and pass `auth_client_token_id` to `VespaCloud`, then use `endpoint_type="token"` in `get_application()`.

---

## Further Reading

- Load `docs/package-api.md` for the complete configuration class reference
- Load `docs/application-api.md` for the full Vespa connection, deployment, and I/O API
- pyvespa documentation: https://vespa-engine.github.io/pyvespa/
- pyvespa examples: https://github.com/vespa-engine/pyvespa/tree/master/docs/sphinx/source
