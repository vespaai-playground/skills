# Passing Query Tensors

Load this reference when passing tensor values as query inputs (for nearest-neighbor search, user-profile embeddings, or multi-feature ranking).

Tensors are passed via `input.query(name)` in the query request.

## Dense Tensor

```json
{ "input.query(q_embedding)": [0.1, 0.05, -0.23, "..."] }
```

Declared as: `query(q_embedding) tensor<float>(x[384])`

## Sparse Tensor (Mapped)

```json
{ "input.query(user_tags)": {"cells": [{"address": {"tag": "ml"}, "value": 1.0}]} }
```

Declared as: `query(user_tags) tensor<float>(tag{})`

## Mixed Tensor

```json
{ "input.query(preferences)": {"blocks": {"sports": [0.1, 0.2], "tech": [0.5, 0.3]}} }
```

Declared as: `query(preferences) tensor<float>(category{}, feature[64])`
