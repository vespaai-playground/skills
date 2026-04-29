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

Vespa can run embedding models as built-in container components (`hugging-face-embedder`, `colbert-embedder`, `splade-embedder`) — the application converts text to vectors at index and query time without calling an external service. Embedders are declared as `<component>` elements inside the container cluster and referenced from a schema's indexing pipeline via `embed <component-id>`.

The canonical declaration uses the `type` shortcut with `<transformer-model>` and `<tokenizer-model>` child elements that point at the model and tokenizer files via their `url` attribute:

```xml
<component id="e5" type="hugging-face-embedder">
  <transformer-model url="https://huggingface.co/intfloat/e5-small-v2/resolve/main/model.onnx"/>
  <tokenizer-model url="https://huggingface.co/intfloat/e5-small-v2/resolve/main/tokenizer.json"/>
</component>
```

Use the `type="hugging-face-embedder"` shortcut rather than the verbose `class="...HuggingFaceEmbedder"` + `<config name="...">` form — the type shortcut is the documented convention.

For other embedder types, GPU acceleration setup, and additional schema integration, load `docs/embedders.md`.

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

The Vespa CLI (`vespa`) deploys application packages, feeds documents, runs queries, and manages authentication. For the full command surface, use the **vespa-cli** skill — it covers every subcommand, flag, auth mode, and CI pattern in depth.

Minimum commands to deploy this application package:

```bash
vespa config set target local   # or 'cloud'
vespa deploy                    # from the application package directory
vespa status --wait 300         # wait for convergence
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

`<redundancy>` must not exceed the number of content nodes. If you set `<redundancy>2</redundancy>` but only have one content node, Vespa will silently clamp the effective redundancy to the node count and emit a warning — deployment still succeeds, but data will not be replicated as configured.

Vespa also accepts `<min-redundancy>` as the now-preferred form. Both work; new applications should use `<min-redundancy>`:

```xml
<content id="my_content" version="1.0">
  <min-redundancy>2</min-redundancy>
  ...
</content>
```

> **For deeper detail**, load `docs/services-xml.md` or `docs/embedders.md` from this skill's directory as needed. Related skills: `schema-authoring` (for `.sd` files), `vespa-cli` (for CLI surface), `feed-operations` (for document CRUD).
