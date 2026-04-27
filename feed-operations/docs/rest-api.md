# REST API — curl Examples

Load this reference when invoking `/document/v1` directly via HTTP (e.g. from shell scripts, non-Java/Python clients, or debugging with curl).

## Endpoint Table

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

## Common Query Parameters

| Parameter | Description |
|---|---|
| `timeout` | Operation timeout, e.g. `5s`, `500ms`. Defaults to server config. |
| `route` | Override the document route, e.g. `default`. Rarely needed. |
| `condition` | Document selection expression for conditional writes. |
| `create` | Boolean. If `true`, an update creates the document if it does not exist (upsert). |
| `tracelevel` | Integer 1-9. Returns trace information for debugging feed pipelines. |

## PUT via curl

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  --data '{"fields":{"artist":"Radiohead","title":"OK Computer","year":1997}}' \
  "http://localhost:8080/document/v1/mynamespace/music/docid/doc-1"
```

## UPDATE via curl

```bash
curl -X PUT \
  -H "Content-Type: application/json" \
  --data '{"fields":{"year":{"assign":1997},"play_count":{"increment":1}}}' \
  "http://localhost:8080/document/v1/mynamespace/music/docid/doc-1"
```

## GET and DELETE via curl

```bash
# Get
curl "http://localhost:8080/document/v1/mynamespace/music/docid/doc-1"

# Delete
curl -X DELETE "http://localhost:8080/document/v1/mynamespace/music/docid/doc-1"
```
