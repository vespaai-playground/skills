# Visit / Export Documents

Load this reference when exporting documents from a cluster, paginating over a large document set, or running a batch over all matches of a selection expression.

Visiting lets you iterate over all (or a subset of) documents in a content cluster.

## CLI

```bash
# Visit all documents of a given type
vespa visit

# Visit with a selection expression
vespa visit --selection "music.year > 2000"

# Limit the number of documents
vespa visit --count 100
```

## REST API

Use `GET /document/v1/` with query parameters for programmatic visiting:

```bash
curl "http://localhost:8080/document/v1/?cluster=content&selection=true&wantedDocumentCount=100"
```

| Parameter | Description |
|---|---|
| `cluster` | The content cluster name (required when more than one cluster exists). |
| `selection` | A document selection expression. Use `true` to visit all documents. |
| `wantedDocumentCount` | Approximate number of documents to return per request. Not a hard limit. |
| `continuation` | Continuation token from a previous response, used to paginate through results. |
| `timeout` | Per-request timeout. |
| `fieldSet` | Which fields to return, e.g. `music:[document]` for all fields, or `[id]` for IDs only. |

## Pagination Pattern

```bash
# First request
RESPONSE=$(curl -s "http://localhost:8080/document/v1/?cluster=content&selection=true&wantedDocumentCount=500")

# Extract continuation token and repeat
CONTINUATION=$(echo "$RESPONSE" | jq -r '.continuation')
curl -s "http://localhost:8080/document/v1/?cluster=content&selection=true&wantedDocumentCount=500&continuation=$CONTINUATION"
```

Repeat until the response no longer contains a `continuation` token, which signals that all matching documents have been visited.

## Selection Expressions

Selection expressions filter which documents are visited (or fed conditionally). Syntax examples:

```
true                                        # all documents
music                                       # all documents of type "music"
music.year > 2000                           # field comparison
music.year > 2000 AND music.genre == "rock" # compound
id.namespace == "tenant_a"                  # filter by namespace
id.group == "customer_abc"                  # filter by group modifier
```
