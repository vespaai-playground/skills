# services.xml Reference

Vespa's `services.xml` is the main deployment descriptor. It declares containers, content clusters,
components, and resource allocation. It lives at the root of the application package.

---

## Root Element

```xml
<services version="1.0">
  <!-- container and content clusters go here -->
</services>
```

The `version` attribute is required and must be `"1.0"`.

---

## `<container>` Element

Declares a stateless container cluster that handles queries, feeding, and custom request processing.

### Attributes

| Attribute | Required | Description                          |
|-----------|----------|--------------------------------------|
| id        | yes      | Unique cluster identifier            |
| version   | yes      | Must be `"1.0"`                      |

### Basic Structure

```xml
<container id="default" version="1.0">
  <document-api/>
  <search/>
  <nodes>
    <node hostalias="node1"/>
  </nodes>
</container>
```

### `<document-api/>`

Enables the `/document/v1/` REST endpoint for feeding (PUT, POST, DELETE, GET) documents.
Without this element, no feeding endpoint is exposed and document operations will return 404.

```xml
<document-api/>
```

### `<search/>`

Enables the `/search/` query endpoint. This is required for any application that serves queries.

```xml
<search/>
```

### `<document-processing/>`

Enables document processor chains. Document processors can transform, validate, or enrich
documents during feeding before they reach the content layer.

```xml
<document-processing/>
```

You can declare custom chains:

```xml
<document-processing>
  <chain id="my-chain">
    <documentprocessor id="com.example.MyProcessor"/>
  </chain>
</document-processing>
```

### `<handler>`

Registers a custom HTTP request handler at one or more URI bindings.

```xml
<handler id="com.example.MyHandler" bundle="my-bundle">
  <binding>http://*/my-endpoint</binding>
  <binding>http://*/my-endpoint/*</binding>
</handler>
```

The `binding` pattern supports wildcards. The handler class must implement
`com.yahoo.container.jdisc.HttpRequestHandler` or extend a convenience base class.

### `<component>`

Registers a custom component (embedder, searcher, processor, or any injectable instance)
in the container's dependency injection framework.

```xml
<component id="my-embedder" type="hugging-face-embedder">
  <transformer-model url="https://huggingface.co/model/resolve/main/model.onnx"/>
  <tokenizer-model url="https://huggingface.co/model/resolve/main/tokenizer.json"/>
</component>
```

Components are referenced by their `id` in schema rank profiles and other configuration.

### `<nodes>`

Specifies the container nodes, resource allocation, and JVM options.

```xml
<nodes jvmargs="-Xms4g -Xmx4g">
  <node hostalias="node1"/>
  <node hostalias="node2"/>
</nodes>
```

For Vespa Cloud, use the `count` and resource attributes:

```xml
<nodes count="2">
  <resources vcpu="4.0" memory="16Gb" disk="50Gb"/>
</nodes>
```

The `jvmargs` attribute sets JVM options for all nodes in the cluster. For Vespa Cloud
deployments, `jvm-options` is preferred over `jvmargs`:

```xml
<nodes count="2" jvm-options="-Xms4g -Xmx4g">
  <resources vcpu="4.0" memory="16Gb" disk="50Gb"/>
</nodes>
```

### `<http>`

Configures HTTP server settings including ports and filtering.

```xml
<http>
  <server id="default" port="8080"/>
  <filtering>
    <access-control domain="my-domain"/>
  </filtering>
</http>
```

### `<clients>`

Configures authentication and authorization for Vespa Cloud deployments. Controls which
data-plane clients can access the application.

```xml
<clients>
  <client id="mtls" permissions="read,write">
    <certificate file="security/clients.pem"/>
  </client>
  <client id="token" permissions="read">
    <token id="my-read-token"/>
  </client>
</clients>
```

---

## `<content>` Element

Declares a stateful content cluster that stores and indexes documents.

### Attributes

| Attribute | Required | Description                                           |
|-----------|----------|-------------------------------------------------------|
| id        | yes      | Cluster identifier, used in `/document/v1/` API URLs  |
| version   | yes      | Must be `"1.0"`                                       |

### Basic Structure

```xml
<content id="music" version="1.0">
  <redundancy>2</redundancy>
  <documents>
    <document type="music" mode="index"/>
  </documents>
  <nodes>
    <node hostalias="node1" distribution-key="0"/>
  </nodes>
</content>
```

### `<redundancy>`

Sets the number of copies of each document stored across the cluster. Recommended value is `2`
for production deployments to tolerate single-node failures. Minimum is `1`.

```xml
<redundancy>2</redundancy>
```

### `<documents>`

Lists the document types served by this content cluster. Each `<document>` element maps to a
schema file in the `schemas/` directory.

```xml
<documents>
  <document type="music" mode="index"/>
  <document type="lyrics" mode="streaming"/>
  <document type="raw_data" mode="store-only"/>
</documents>
```

#### Document Modes

| Mode         | Description                                                        |
|--------------|--------------------------------------------------------------------|
| `index`      | Default. Full indexing and search support with match/rank features. |
| `streaming`  | Data stored on disk, streamed at query time. Requires a group/selection in the query. Best for per-user or per-session data where each query targets a small subset. |
| `store-only` | No indexing or searching. Documents can only be accessed by ID. Useful for document types that are joined at query time or used only for processing. |

### `<nodes>`

Specifies content nodes. Each node needs a unique `distribution-key`.

```xml
<nodes>
  <node hostalias="node1" distribution-key="0"/>
  <node hostalias="node2" distribution-key="1"/>
</nodes>
```

For Vespa Cloud:

```xml
<nodes count="3">
  <resources vcpu="2.0" memory="8Gb" disk="100Gb"/>
</nodes>
```

#### Multi-Group Setup

Groups distribute data across failure domains. Useful for high-availability deployments.

```xml
<nodes>
  <group>
    <distribution partitions="1|*"/>
    <group distribution-key="0" name="group0">
      <node hostalias="node0" distribution-key="0"/>
      <node hostalias="node1" distribution-key="1"/>
    </group>
    <group distribution-key="1" name="group1">
      <node hostalias="node2" distribution-key="2"/>
      <node hostalias="node3" distribution-key="3"/>
    </group>
  </group>
</nodes>
```

### `<engine>`

Tunes the proton search engine (content node internals). Rarely needed for most applications.

```xml
<engine>
  <proton>
    <flush>
      <memory>512000000</memory>
    </flush>
    <feeding>
      <concurrency>0.5</concurrency>
    </feeding>
    <searchable-copies>1</searchable-copies>
  </proton>
</engine>
```

### `<dispatch>`

Configures how queries are dispatched to content nodes within the cluster.

```xml
<dispatch>
  <num-dispatch-groups>2</num-dispatch-groups>
</dispatch>
```

### `<tuning>`

Tunes cluster-level parameters such as resource limits and bucket splitting.

```xml
<tuning>
  <resource-limits>
    <disk>0.8</disk>
    <memory>0.8</memory>
  </resource-limits>
  <bucket-splitting minimum-bits="16"/>
</tuning>
```

Resource limits define the threshold (fraction of total available) at which the node will
stop accepting writes to protect cluster stability. The defaults are `0.8` for both.

---

## Embedder Configuration

### Hugging Face Embedder

```xml
<component id="my-embedder" type="hugging-face-embedder">
  <transformer-model url="https://huggingface.co/BAAI/bge-small-en-v1.5/resolve/main/model.onnx"/>
  <tokenizer-model url="https://huggingface.co/BAAI/bge-small-en-v1.5/resolve/main/tokenizer.json"/>
  <transformer-token-type-ids/>
  <prepend>
    <query>query: </query>
    <document>passage: </document>
  </prepend>
</component>
```

Reference it in a schema rank profile:

```
input.query(q) = embed(my-embedder, @query)
```

### ColBERT Embedder

```xml
<component id="my-colbert" type="colbert-embedder">
  <transformer-model url="https://huggingface.co/colbert-ir/colbertv2.0/resolve/main/model.onnx"/>
  <tokenizer-model url="https://huggingface.co/colbert-ir/colbertv2.0/resolve/main/tokenizer.json"/>
  <max-query-tokens>32</max-query-tokens>
  <max-document-tokens>512</max-document-tokens>
</component>
```

### Custom Embedder via Component

```xml
<component id="my-custom-embedder" class="com.example.MyEmbedder" bundle="my-bundle">
  <config name="com.example.my-embedder">
    <modelPath>models/custom-model.onnx</modelPath>
    <vocabPath>models/vocab.txt</vocabPath>
  </config>
</component>
```

The class must implement `com.yahoo.language.process.Embedder`.

---

## Resource Sizing Guidelines

### Memory

- **Container nodes**: minimum 4 GB; 8-16 GB typical for embedder workloads. The JVM heap
  should be sized to leave room for ONNX model inference (native memory).
- **Content nodes**: depends on index size. Estimate ~2x the raw document data for indexed
  mode. Streaming mode uses significantly less memory since data is disk-resident.

### vCPU

- **Container nodes**: 2-8 vCPU. Embedding inference benefits from higher core counts.
  Scale horizontally (more nodes) rather than vertically for throughput.
- **Content nodes**: 2-4 vCPU typical. More cores help with concurrent query matching.

### Disk

- **Content nodes**: estimate 3-4x raw document size for `index` mode (includes index
  structures, transaction logs, and redundancy). For `streaming` mode, 1.5-2x is typical.
- Use `vespa-proton-cmd` on running nodes to monitor actual usage.

---

## Multi-Cluster Setups

An application can have multiple content clusters, each serving different document types
or workloads.

```xml
<services version="1.0">
  <container id="default" version="1.0">
    <document-api/>
    <search/>
    <nodes count="2">
      <resources vcpu="4.0" memory="16Gb" disk="50Gb"/>
    </nodes>
  </container>

  <content id="products" version="1.0">
    <redundancy>2</redundancy>
    <documents>
      <document type="product" mode="index"/>
    </documents>
    <nodes count="3">
      <resources vcpu="2.0" memory="8Gb" disk="100Gb"/>
    </nodes>
  </content>

  <content id="reviews" version="1.0">
    <redundancy>2</redundancy>
    <documents>
      <document type="review" mode="index"/>
    </documents>
    <nodes count="2">
      <resources vcpu="2.0" memory="8Gb" disk="50Gb"/>
    </nodes>
  </content>
</services>
```

Queries target a specific content cluster via the `sources` parameter:

```
/search/?query=shoes&sources=products
```

---

## Global Documents

A global document is replicated to every content node, making it available for local joins
in rank expressions without network lookups. Use for small reference datasets (categories,
configuration tables).

```xml
<documents>
  <document type="category" mode="index" global="true"/>
  <document type="product" mode="index"/>
</documents>
```

Global documents increase memory usage proportionally across all nodes. Keep them small.

---

## Complete Example: Hybrid Search App with Embedder

```xml
<services version="1.0">

  <container id="default" version="1.0">
    <document-api/>
    <search/>
    <document-processing/>

    <component id="e5-small" type="hugging-face-embedder">
      <transformer-model url="https://huggingface.co/intfloat/e5-small-v2/resolve/main/model.onnx"/>
      <tokenizer-model url="https://huggingface.co/intfloat/e5-small-v2/resolve/main/tokenizer.json"/>
      <prepend>
        <query>query: </query>
        <document>passage: </document>
      </prepend>
    </component>

    <nodes count="2">
      <resources vcpu="4.0" memory="16Gb" disk="50Gb"/>
    </nodes>

    <clients>
      <client id="mtls" permissions="read,write">
        <certificate file="security/clients.pem"/>
      </client>
    </clients>
  </container>

  <content id="docs" version="1.0">
    <redundancy>2</redundancy>
    <documents>
      <document type="doc" mode="index"/>
    </documents>
    <nodes count="3">
      <resources vcpu="2.0" memory="8Gb" disk="100Gb"/>
    </nodes>
    <tuning>
      <resource-limits>
        <disk>0.8</disk>
        <memory>0.8</memory>
      </resource-limits>
    </tuning>
  </content>

</services>
```

This configures:
- A container cluster with feeding, search, and a Hugging Face embedder for hybrid (BM25 + vector) search.
- A content cluster with redundancy 2, storing `doc` documents in indexed mode.
- mTLS client authentication for Vespa Cloud.

---

## Common Mistakes

**Forgetting `<document-api/>`**: Without this element in `<container>`, the
`/document/v1/` feeding endpoint is not available. Feeding requests will return 404.
This is the most frequent omission.

**Wrong document type name**: The `type` attribute in `<document type="X">` must exactly
match the schema file name (`schemas/X.sd`). A mismatch causes a deployment failure with
a message about an unknown document type.

**Memory limits too low**: Content nodes that run out of memory will stop accepting writes
(blocked feeds). The `<tuning><resource-limits><memory>` setting controls the threshold.
If your nodes are near capacity, either add nodes or increase the limit cautiously.

**Missing schema file**: Every document type referenced in `services.xml` must have a
corresponding `.sd` file in the `schemas/` directory. Deployment fails otherwise.

**Redundancy higher than node count**: Setting `<redundancy>3</redundancy>` with only 2
content nodes means the third copy has nowhere to go. Vespa will warn and effectively
use the node count as the redundancy.

**Embedding model not found at URL**: The `url` attribute for `transformer-model` must
point to a direct-download ONNX file. Hugging Face URLs must use the `/resolve/main/`
path, not the web UI path.
