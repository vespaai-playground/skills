# Extended Schema Gotchas

Load this reference when debugging unexpected schema behavior, validating an existing schema, or resolving deployment errors. The top 4 most common gotchas are inline in SKILL.md; this file covers the rest.

**5. Memory pressure from attributes.** Every attribute is in-memory. Use `attribute: paged` for large or rarely-accessed attribute fields.

**6. Type changes on live systems.** Requires reindexing and `validation-overrides.xml`.

**7. Missing `summary`.** Fields without `summary` in their indexing pipeline are not returned in results.

**8. `raw` is not searchable.** Only use for binary blobs that need storage and retrieval.

**9. Weightedset type restrictions.** Element type must be `string`, `int`, or `long`.

**10. Reference fields require `attribute` only.** No `index`. Use `import field` for parent fields:

```sd
schema child {
    document child {
        field parent_ref type reference<parent> { indexing: attribute }
    }
    import field parent_ref.name as parent_name {}
}
```

**11. `fast-access` on predicate, tensor, and reference attributes.** They are not supported.

**12. `fast-search` on dense tensor fields.** `fast-search` only works for boolean, numeric, strings, and tensors with at least a mapped dimension.
