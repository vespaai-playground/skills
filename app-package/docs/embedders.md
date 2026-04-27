# Embedder Configuration

Load this reference when configuring built-in embedder components in `services.xml` (Hugging Face, ColBERT, SPLADE) or enabling GPU acceleration for inference.

Vespa supports embedding models as built-in components inside the container cluster. This lets the application convert text to vectors at query time and indexing time without an external service.

## Hugging Face Embedder

The `hugging-face-embedder` component loads a Hugging Face tokenizer and an ONNX embedding model:

```xml
<container id="default" version="1.0">
  <document-api/>
  <search/>

  <component id="my_embedder" type="hugging-face-embedder">
    <!-- Path to the HF tokenizer.json file -->
    <transformer-model url="https://huggingface.co/e5-small-v2/resolve/main/model.onnx"/>
    <tokenizer-model url="https://huggingface.co/e5-small-v2/resolve/main/tokenizer.json"/>

    <!-- Maximum number of tokens per input -->
    <max-tokens>512</max-tokens>

    <!-- Transformer token type IDs (pooling strategy) -->
    <pooling-strategy>mean</pooling-strategy>
  </component>

  <nodes count="2">
    <resources vcpu="4.0" memory="16Gb" disk="100Gb"/>
  </nodes>
</container>
```

You reference the embedder in a schema like this:

```
field my_embedding type tensor<float>(x[384]) {
    indexing: input my_text | embed my_embedder | attribute | index
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

## GPU Acceleration for Embedders

On Vespa Cloud, enable GPU for inference on embedder components:

```xml
<container id="default" version="1.0">
  <document-api/>
  <search/>

  <component id="my_embedder" type="hugging-face-embedder">
    <transformer-model url="https://huggingface.co/model/resolve/main/model.onnx"/>
    <tokenizer-model url="https://huggingface.co/model/resolve/main/tokenizer.json"/>
  </component>

  <nodes count="1">
    <resources vcpu="4.0" memory="16Gb" disk="100Gb">
      <gpu count="1" memory="16Gb"/>
    </resources>
  </nodes>
</container>
```

## Other Embedders

Vespa provides additional built-in embedder types:

**ColBERT Embedder** — produces multi-token tensor representations for late-interaction retrieval (MaxSim):

```xml
<component id="my_colbert" type="colbert-embedder">
  <transformer-model url="https://huggingface.co/colbert-model/resolve/main/model.onnx"/>
  <tokenizer-model url="https://huggingface.co/colbert-model/resolve/main/tokenizer.json"/>
  <max-tokens>512</max-tokens>
</component>
```

**SPLADE Embedder** — produces sparse learned representations:

```xml
<component id="my_splade" type="splade-embedder">
  <transformer-model url="https://huggingface.co/splade-model/resolve/main/model.onnx"/>
  <tokenizer-model url="https://huggingface.co/splade-model/resolve/main/tokenizer.json"/>
</component>
```

Refer to the Vespa documentation for the full list of embedder types and their configuration options.
