# Vespa Advanced Schema Patterns

Reference for advanced schema design patterns including inheritance, document relationships, streaming mode, expiry, and multi-schema applications.

## Parent-Child Document Relationships

Parent-child relationships let child documents access fields from parent documents at query time without denormalization. The parent field values are resolved via in-memory joins.

### Declaring the Parent Schema

```sd
schema brand {
    document brand {
        field brand_name type string {
            indexing: attribute | summary
        }
        field brand_tier type string {
            indexing: attribute | summary
        }
    }
}
```

The parent must be declared as a **global document** in `services.xml`:

```xml
<content id="content" version="1.0">
    <documents>
        <document type="brand" mode="index" global="true" />
        <document type="product" mode="index" />
    </documents>
</content>
```

### Declaring the Child Schema with Reference and Import

```sd
schema product {
    document product {
        field title type string {
            indexing: index | summary
        }
        field brand_ref type reference<brand> {
            indexing: attribute | summary
        }
    }

    # import is declared outside the document block
    import field brand_ref.brand_name as brand_name {}
    import field brand_ref.brand_tier as brand_tier {}
}
```

### Key Rules for Parent-Child

- The `reference<parent_type>` field must be `attribute`.
- The parent document type must have `global="true"` in services.xml -- global documents are replicated to all content nodes so that joins are always local.
- `import field` is declared at schema level, outside the `document { }` block.
- Imported fields behave like local attribute fields: they can be used in filtering, sorting, grouping, and ranking.
- Imported fields are read-only projections; you cannot write to them directly.
- A document can reference multiple parent types.
- Parent documents cannot themselves contain `reference` fields (no multi-hop references).

## Document Inheritance

Document inheritance allows a child document to inherit fields from a parent document definition.

```sd
schema product_review {
    document product_review inherits product {
        field review_text type string {
            indexing: index | summary
        }
        field rating type int {
            indexing: attribute | summary
        }
    }
}
```

### What Document Inheritance Does

- The child document includes all fields defined in the parent `document` block.
- Child can add new fields but cannot override or remove inherited fields.
- Both parent and child are independent document types in the content cluster -- inheriting fields does not create a parent-child query-time join.
- Feeding a `product_review` requires providing values for both inherited `product` fields and the child's own fields.

### What Document Inheritance Does NOT Do

- It does NOT create a parent-child relationship (use `reference<>` + `import field` for that).
- It does NOT allow querying across parent and child types automatically.
- It does NOT share stored data between documents; each document is self-contained.

## Schema Inheritance

Schema inheritance is separate from document inheritance. It inherits the entire schema definition: document fields, rank profiles, fieldsets, summaries, and other schema-level constructs.

```sd
schema detailed_product inherits product {
    document detailed_product inherits product {
        field specifications type map<string, string> {
            indexing: summary
            struct-field key   { indexing: attribute }
            struct-field value { indexing: attribute }
        }
    }

    # Inherits all rank profiles, fieldsets, and document-summaries from product
    # Can add or override rank profiles
    rank-profile detailed_ranking inherits default {
        first-phase {
            expression: bm25(title) + attribute(popularity) * 0.1
        }
    }
}
```

### Document Inheritance vs Schema Inheritance

| Aspect | Document Inheritance | Schema Inheritance |
|--------|--------------------|--------------------|
| Syntax | `document child inherits parent` | `schema child inherits parent` |
| Scope | Only fields in the `document { }` block | Entire schema: fields, rank profiles, fieldsets, summaries |
| Typically used together | Yes -- if schema inherits, document usually inherits too | Schema inheritance without document inheritance is unusual |
| Runtime join | No | No |
| Data sharing | No -- documents are independent copies | No -- documents are independent copies |
| Use case | Reuse common field definitions | Reuse common field definitions + rank profiles + summaries |

In practice, you almost always use both together: `schema child inherits parent { document child inherits parent { ... } }`.

## Streaming Mode

Streaming mode stores documents as serialized blobs and evaluates queries by streaming through all documents in a bucket rather than using inverted indexes.

### Configuration in services.xml

```xml
<content id="content" version="1.0">
    <documents>
        <document type="user_mail" mode="streaming" />
    </documents>
</content>
```

### When to Use Streaming Mode

- **Per-user or per-group data**: When every query targets a specific user/group and you always supply a group ID in the query. Vespa streams only that group's documents.
- **Many small document types**: When you have thousands or millions of small document sets, each queried independently.
- **Low query fan-out**: Queries that always include a selection (group restriction) so Vespa does not scan the entire corpus.
- **Rich schema features without index cost**: All field types and matching modes work, but without building inverted indexes, HNSW graphs, etc.

### When NOT to Use Streaming Mode

- Open-ended search across the full corpus (no group restriction).
- Low-latency requirements over millions of documents without group partitioning.
- Nearest-neighbor search at scale (no HNSW index in streaming mode; brute-force only).

### Query-Time Group Restriction

Queries in streaming mode must restrict to a group using the `streaming.groupname` parameter:

```
/search/?query=subject:meeting&streaming.groupname=user123
```

### Implications

- No inverted indexes, B-trees, or HNSW graphs are built. All matching is brute-force within the selected group.
- Drastically lower write-path cost (no index maintenance).
- Memory footprint is minimal since documents are stored on disk, not in memory attributes (unless explicitly configured).
- Rank profiles and all YQL query operators still work.
- Ideal storage cost profile for long-tail, per-tenant data.

## Store-Only Mode

Store-only mode stores documents without any indexing or search capability. Documents can only be retrieved by document ID.

```xml
<content id="content" version="1.0">
    <documents>
        <document type="raw_event" mode="store-only" />
    </documents>
</content>
```

### Use Cases

- Archival or audit log storage where you only need GET-by-ID.
- Raw event storage for later batch processing.
- Backing store where search is handled by an external system.

### Limitations

- No queries, matching, or ranking. Only `document/v1` GET/PUT/DELETE operations.
- No attributes, no indexes, no summaries beyond document retrieval.

## Document Expiry and Garbage Collection

Vespa can automatically remove documents based on time-based or selection expressions.

### Time-Based Expiry (GC Selection)

In `services.xml`, use the `selection` attribute on the document type:

```xml
<content id="content" version="1.0">
    <documents>
        <document type="news_article" mode="index"
                  selection="news_article.publish_timestamp > now() - 2592000" />
    </documents>
    <engine>
        <proton>
            <tuning>
                <searchnode>
                    <lidspace>
                        <max-bloat-factor>0.2</max-bloat-factor>
                    </lidspace>
                </searchnode>
            </tuning>
        </proton>
    </engine>
</content>
```

### Key Requirements for Document Expiry

- The timestamp field (`publish_timestamp` above) must be of type `long` and stored as `attribute`.
- The value must be in seconds since Unix epoch (not milliseconds).
- `now()` returns the current time in seconds since epoch.
- The expression `2592000` equals 30 days in seconds (30 * 86400).
- Garbage collection runs periodically in the background; documents are not removed instantly.
- The `max-bloat-factor` controls how aggressively lid space (document ID slots) is compacted after removals.

### Selection Expression Syntax

The selection language supports:

```
document_type.field_name > now() - <seconds>
document_type.field_name == "value"
document_type.field_name != null
(expression1) AND (expression2)
(expression1) OR (expression2)
NOT (expression)
```

Example combining conditions:

```xml
<document type="log_entry" mode="index"
          selection="log_entry.created_at > now() - 86400 AND log_entry.level != 'DEBUG'" />
```

## Global Documents

Global documents are replicated to every content node. They are required for parent documents in reference relationships and useful for small, frequently accessed reference data.

```xml
<content id="content" version="1.0">
    <documents>
        <document type="category" mode="index" global="true" />
    </documents>
</content>
```

### When to Use Global Documents

- Parent document types referenced via `reference<>` fields (mandatory).
- Small reference/lookup tables (e.g., categories, brands, config) used in ranking or filtering across all queries.
- Data that must be available on every node for local join resolution.

### When NOT to Use Global Documents

- Large document sets (millions of documents) -- each document is replicated to every node, multiplying storage.
- Documents that change frequently -- updates must propagate to all nodes.
- Primary search corpus -- use normal (non-global) distribution for large-scale search.

### Cost Model

Storage cost = `document_count * document_size * number_of_content_nodes`. A 1 GB global dataset on 10 nodes costs 10 GB total.

## Struct Patterns

Structs group related fields into a single unit within a document.

```sd
schema product {
    document product {
        struct dimension {
            field width type double {}
            field height type double {}
            field depth type double {}
            field unit type string {}
        }

        field dimensions type dimension {
            indexing: summary
            struct-field width  { indexing: attribute }
            struct-field height { indexing: attribute }
        }

        field size_variants type array<dimension> {
            indexing: summary
            struct-field width  { indexing: attribute }
            struct-field height { indexing: attribute }
        }
    }
}
```

### When to Use Struct vs Separate Document Type

| Use struct when... | Use separate document type when... |
|---|---|
| Data is always read and written together with the parent | Data has its own lifecycle (created/updated independently) |
| No need to query the sub-data independently | Need to search for the nested entity on its own |
| Cardinality is bounded (e.g., a product has one dimensions block) | Cardinality is unbounded or very large (e.g., millions of reviews) |
| No cross-document references needed | Other documents need to reference it |

### Struct Limitations

- Struct fields cannot be `index` (no tokenized text search on struct sub-fields).
- Struct fields are accessed via `struct-field` directive for attribute/filtering.
- Structs cannot contain `reference<>` fields.
- Structs cannot be used with `import field`.

## Annotation and Summary Class Patterns

### Document Summaries

Document summaries control what fields are returned in search results, reducing network transfer.

```sd
schema article {
    document article {
        field title type string {
            indexing: index | summary
        }
        field body type string {
            indexing: index | summary
        }
        field internal_score type float {
            indexing: attribute
        }
    }

    document-summary short_summary {
        summary title {}
        # body is excluded -- not transferred in this summary class
    }

    document-summary full_summary inherits default {
        summary body {
            bolding: on        # highlight matching query terms with <hi> tags
            source: body
        }
    }
}
```

### Bolding and Dynamic Snippets

```sd
document-summary snippet_summary {
    summary title {
        bolding: on                  # wraps matching terms in <hi>...</hi>
    }
    summary body {
        bolding: on
        dynamic                      # generates a snippet around matching terms
        # 'dynamic' creates a short excerpt with <hi> tags rather than full field
    }
}
```

- `bolding: on` wraps query-matched tokens in `<hi>` tags in the summary output.
- `dynamic` truncates the field to a snippet window around matched terms, with `<hi>` tags. Only valid on string fields with `index`.
- Request a specific summary class at query time: `&summary=snippet_summary` or via YQL `select * from sources * where ... | all(summary snippet_summary)`.

## Multi-Schema Applications

A Vespa application can contain multiple `.sd` schema files, each defining a separate document type and search configuration.

### File Layout

```
application/
    schemas/
        product.sd
        review.sd
        brand.sd
    services.xml
    hosts.xml
```

### services.xml Declaration

```xml
<content id="content" version="1.0">
    <documents>
        <document type="product" mode="index" />
        <document type="review" mode="index" />
        <document type="brand" mode="index" global="true" />
    </documents>
</content>
```

### Cross-Schema Considerations

- **Querying multiple types**: Use `sources` in YQL to target specific schemas: `select * from sources product, review where ...`. By default, all schemas in the content cluster are searched.
- **Shared rank profiles**: Use schema inheritance to share rank profiles across types.
- **Fieldsets across types**: Each schema has its own `fieldset` definitions. A field with the same name in two schemas does not automatically form a cross-schema fieldset.
- **Document references**: A child schema can reference a parent schema's document via `reference<parent_type>`. The parent must be `global`.
- **Separate content clusters**: For different performance profiles, you can place different schemas in separate `<content>` clusters in services.xml, each with its own resource allocation and redundancy settings.

### Schema File Naming

- The file name must match the schema name: `schema product { ... }` must be in `product.sd`.
- Schema names must be valid identifiers (alphanumeric and underscore, starting with a letter).

## Summary of Mode Selection

| Mode | Declared In | Index Built | Queryable | Use Case |
|------|-------------|-------------|-----------|----------|
| `index` (default) | services.xml | Yes | Full search, filter, rank | Standard search applications |
| `streaming` | services.xml | No | Full query language, but brute-force within group | Per-user/per-group data, mail, personal docs |
| `store-only` | services.xml | No | GET-by-ID only | Archival, raw storage, external search |

## Pattern Decision Guide

| Scenario | Recommended Pattern |
|----------|-------------------|
| Small lookup table used in ranking | Global document + reference + import field |
| Per-user email search | Streaming mode with user as group |
| Shared fields across multiple doc types | Document inheritance or schema inheritance |
| Time-limited data (e.g., news, logs) | Document expiry via `selection` in services.xml |
| Nested object with bounded cardinality | Struct with struct-field attribute declarations |
| Nested object with independent lifecycle | Separate document type |
| Multiple result formats for same data | Multiple document-summary classes |
| Search result highlighting | `bolding: on` + `dynamic` in summary |
