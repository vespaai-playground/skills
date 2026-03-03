---
name: "app-package"
description: "Scaffold and configure Vespa application packages, including services.xml, schemas, deployment.xml, query profiles, and embedder components."
---

# Vespa Application Package

## Overview

A Vespa **application package** is the set of configuration files that together define the behavior of a Vespa application. It tells Vespa which document types to store, how to index and rank them, which clusters to create, and how to expose search and feed APIs. You deploy an application package as a unit -- Vespa validates the entire package before activating it.

An application package is a directory (or a compressed `.zip`) containing at minimum:

- `services.xml` -- cluster topology and component wiring
- One or more schema files under `schemas/` -- document types, indexing, ranking

Everything else (query profiles, models, constants, security certificates) is optional and added as the application grows.

## Directory Layout

A typical application package has the following structure:

```
myapp/
├── schemas/
│   └── my_doc.sd
├── search/
│   └── query-profiles/
│       ├── default.xml
│       └── types/
│           └── root.xml
├── services.xml
├── deployment.xml (optional, for Vespa Cloud)
└── security/ (optional, for Vespa Cloud)
    └── clients.pem
```

| Path | Purpose |
|---|---|
| `schemas/*.sd` | Schema definitions: fields, fieldsets, rank profiles, document summaries |
| `services.xml` | Declares container and content clusters, components, and node counts |
| `search/query-profiles/` | Query profile defaults and type declarations |
| `deployment.xml` | Vespa Cloud deployment configuration (regions, instances) |
| `security/clients.pem` | mTLS client certificates for Vespa Cloud data-plane authentication |
| `components/*.jar` | Custom Java components (searchers, document processors, handlers) |
| `files/` | Arbitrary files accessible at runtime via the application package API |
| `models/` | Machine-learned models (ONNX, TensorFlow, etc.) |
| `constants/` | Named tensor constants used in ranking |

## services.xml

`services.xml` is the heart of the application package. It declares the clusters, their components, and the document types they serve.

### Complete Template

```xml
<?xml version="1.0" encoding="utf-8" ?>
<services version="1.0">

  <!-- Container cluster: handles HTTP requests (feed, search, processing) -->
  <container id="default" version="1.0">

    <!-- Exposes /document/v1/ endpoint for feeding documents -->
    <document-api/>

    <!-- Exposes /search/ endpoint for queries -->
    <search/>

    <!-- Nodes in this container cluster -->
    <nodes>
      <node hostalias="node1"/>
    </nodes>

  </container>

  <!-- Content cluster: stores and indexes documents, executes ranking -->
  <content id="content" version="1.0">

    <!-- Minimum redundancy: how many copies of each document to keep -->
    <redundancy>1</redundancy>

    <!-- Which document types this content cluster serves -->
    <documents>
      <document type="my_doc" mode="index"/>
    </documents>

    <!-- Nodes in this content cluster -->
    <nodes>
      <node hostalias="node1" distribution-key="0"/>
    </nodes>

  </content>

</services>
```

### Vespa Cloud services.xml

On Vespa Cloud, use resource specifications instead of explicit hosts:

```xml
<?xml version="1.0" encoding="utf-8" ?>
<services version="1.0">

  <container id="default" version="1.0">
    <document-api/>
    <search/>
    <nodes count="2">
      <resources vcpu="4.0" memory="16Gb" disk="100Gb"/>
    </nodes>
  </container>

  <content id="content" version="1.0">
    <redundancy>2</redundancy>
    <documents>
      <document type="my_doc" mode="index"/>
    </documents>
    <nodes count="2">
      <resources vcpu="4.0" memory="16Gb" disk="100Gb"/>
    </nodes>
  </content>

</services>
```

## Embedder Configuration

Vespa supports embedding models as built-in components inside the container cluster. This lets the application convert text to vectors at query time and indexing time without an external service.

### Hugging Face Embedder

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

### GPU Acceleration for Embedders

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

### Other Embedders

Vespa provides additional built-in embedder types:

**ColBERT Embedder** -- produces multi-token tensor representations for late-interaction retrieval (MaxSim):

```xml
<component id="my_colbert" type="colbert-embedder">
  <transformer-model url="https://huggingface.co/colbert-model/resolve/main/model.onnx"/>
  <tokenizer-model url="https://huggingface.co/colbert-model/resolve/main/tokenizer.json"/>
  <max-tokens>512</max-tokens>
</component>
```

**SPLADE Embedder** -- produces sparse learned representations:

```xml
<component id="my_splade" type="splade-embedder">
  <transformer-model url="https://huggingface.co/splade-model/resolve/main/model.onnx"/>
  <tokenizer-model url="https://huggingface.co/splade-model/resolve/main/tokenizer.json"/>
</component>
```

Refer to the Vespa documentation for the full list of embedder types and their configuration options.

## deployment.xml

`deployment.xml` is used only for Vespa Cloud deployments. It controls which instances, environments, and regions the application is deployed to.

### Minimal Example

```xml
<deployment version="1.0">
  <prod>
    <region>aws-us-east-1c</region>
  </prod>
</deployment>
```

### Full Example with Multiple Regions and Test

```xml
<deployment version="1.0">
  <!-- Instance name (appears in the endpoint URL) -->
  <instance id="default">

    <!-- Automatically run system and staging tests before production deploy -->
    <test/>
    <staging/>

    <prod>
      <region>aws-us-east-1c</region>
      <region>aws-eu-west-1a</region>
    </prod>

  </instance>
</deployment>
```

## Query Profiles

Query profiles set default query parameters and declare custom parameter types.

### search/query-profiles/default.xml

```xml
<query-profile id="default">
  <field name="maxHits">10</field>
  <field name="ranking.profile">default</field>
</query-profile>
```

### search/query-profiles/types/root.xml

```xml
<query-profile-type id="root">
  <field name="ranking.features.query(q_embedding)" type="tensor&lt;float&gt;(x[384])"/>
</query-profile-type>
```

The type declaration is required when passing tensor values as query parameters (for example, query embeddings for nearest-neighbor search).

## CLI Commands

The Vespa CLI (`vespa`) is used for deploying, feeding, querying, and managing applications.

### Deploy

```bash
# Deploy the application package in the current directory
vespa deploy

# Deploy a specific application package directory
vespa deploy myapp/

# Deploy to Vespa Cloud (requires authentication)
vespa deploy --target cloud

# Deploy to a specific Vespa Cloud instance
vespa deploy --target cloud --instance my-instance
```

### Status

```bash
# Check the status of the Vespa deployment
vespa status

# Wait for deployment to converge (up to N seconds)
vespa status --wait 300
```

### Configuration

```bash
# Set the target for CLI commands
vespa config set target local         # http://localhost:8080 (default)
vespa config set target cloud         # Vespa Cloud
vespa config set target http://vespa-host:8080

# Set application for Vespa Cloud
vespa config set application my-tenant.my-app

# Set instance for Vespa Cloud
vespa config set instance my-instance

# View current configuration
vespa config get
```

### Authentication (Vespa Cloud)

```bash
# Log in to Vespa Cloud
vespa auth login

# Create a data-plane certificate for your application
vespa auth cert
```

### Clone a Sample Application

```bash
# List available sample applications
vespa clone -l

# Clone a specific sample application
vespa clone album-recommendation myapp/
```

### Feeding Documents

```bash
# Feed a single JSON document
vespa document put my_doc.json

# Feed a JSON-lines file (one operation per line)
vespa feed docs.jsonl

# Feed with a specific target
vespa feed --target http://localhost:8080 docs.jsonl
```

### Querying

```bash
# Run a simple query
vespa query "select * from my_doc where true"

# Run a query with YQL and parameters
vespa query "yql=select * from my_doc where userQuery()" "query=search terms"

# Run a query with a specific ranking profile
vespa query "yql=select * from my_doc where true" "ranking.profile=my_rank"
```

### Document Operations

```bash
# Get a document by ID
vespa document get id:mynamespace:my_doc::1

# Update a document
vespa document update my_update.json

# Delete a document
vespa document remove id:mynamespace:my_doc::1
```

## Gotchas and Common Mistakes

### document-api is required for feeding

If `<document-api/>` is missing from the container cluster in `services.xml`, the `/document/v1/` endpoint will not be available and feed operations will fail with a 404 or connection error. Always include it:

```xml
<container id="default" version="1.0">
  <document-api/>  <!-- Required for feeding via /document/v1/ -->
  <search/>
  <nodes>
    <node hostalias="node1"/>
  </nodes>
</container>
```

### Schema name must match document name

The schema file name, the `schema` declaration, and the `document` declaration inside it must all use the same name. The `document type` referenced in `services.xml` must also match.

```
# File: schemas/my_doc.sd
schema my_doc {
    document my_doc {
        ...
    }
}
```

In `services.xml`:

```xml
<documents>
  <document type="my_doc" mode="index"/>
</documents>
```

If these names do not match, deployment will fail with a validation error.

### Application name constraints

- Application names in Vespa Cloud must consist of lowercase letters, digits, and hyphens only.
- The name cannot start or end with a hyphen.
- Maximum length is 20 characters for tenant name and 20 characters for application name.

### Content cluster id naming

The `id` attribute on `<content>` must be a valid identifier (letters, digits, underscores). Avoid hyphens in the content cluster id because it is used to generate internal metric dimensions and config IDs where hyphens can cause issues. Use underscores instead:

```xml
<!-- Good -->
<content id="my_content" version="1.0">

<!-- Avoid -->
<content id="my-content" version="1.0">
```

### Document mode must be explicit

Always set the `mode` attribute on `<document>` inside `<documents>`. The valid modes are:

- `index` -- full indexing, searching, and ranking (most common)
- `streaming` -- streaming search, no indexing, suited for personal/per-group data
- `store-only` -- store documents but do not index them for search

```xml
<documents>
  <document type="my_doc" mode="index"/>
</documents>
```

### Redundancy and content node count

`<redundancy>` must not exceed the number of content nodes. If you set `<redundancy>2</redundancy>` but only have one content node, deployment will emit a warning and data will not be fully redundant.

## Further Reading

For detailed element-by-element reference of `services.xml`, load the companion file:

```
docs/services-xml.md
```

This file contains the full specification of every element, attribute, and allowed nesting in `services.xml`, including advanced container and content cluster options, document-processing chains, and handler configuration.
