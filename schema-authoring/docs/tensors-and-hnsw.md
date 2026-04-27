# Tensor Fields and HNSW Configuration

Load this reference when defining tensor fields, configuring HNSW indexes for ANN search, or choosing a distance metric.

## Tensor Type Syntax

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

## Distance Metrics

| Metric | When to use |
|---|---|
| `euclidean` | General-purpose; magnitude matters |
| `angular` | Direction matters; any normalization |
| `dotproduct` | Pre-normalized vectors; max inner product |
| `prenormalized-angular` | Already L2-normalized vectors (saves computation) |
| `hamming` | Binary hash codes, int8 quantized vectors |
| `geodegrees` | Geographic coordinate points |

## HNSW Parameters

| Parameter | Default | Guidance |
|---|---|---|
| `max-links-per-node` | 16 | Higher = better recall, more memory. Range: 8-32. |
| `neighbors-to-explore-at-insert` | 200 | Higher = better graph, slower feeding. Range: 100-500. |

Query-time exploration is controlled by `hnsw.exploreAdditionalHits` and `approximate` query parameters, not by the schema.
