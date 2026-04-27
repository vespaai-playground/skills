# Complete Example: E-Commerce Product Schema

Load this reference when designing a production e-commerce schema or looking for a comprehensive example that combines BM25, semantic search, structs, maps, weighted sets, and phased ranking.

```sd
schema product {
    document product {
        struct price_range {
            field min type double {}
            field max type double {}
            field currency type string {}
        }
        field product_id type string {
            indexing: summary | attribute
            attribute: fast-search
        }
        field title type string {
            indexing: summary | index
            index: enable-bm25
            bolding: on
        }
        field description type string {
            indexing: summary | index
            index: enable-bm25
            summary: dynamic
        }
        field brand type string {
            indexing: summary | index | attribute
            match: word
            attribute: fast-search
            rank: filter
        }
        field category type array<string> {
            indexing: summary | attribute
            attribute: fast-search
        }
        field tags type weightedset<string> {
            indexing: summary | attribute
        }
        field price type double {
            indexing: summary | attribute
            attribute: fast-search
        }
        field sale_price type price_range {
            indexing: summary
            struct-field min      { indexing: attribute }
            struct-field max      { indexing: attribute }
            struct-field currency { indexing: attribute  match: exact }
        }
        field in_stock type bool {
            indexing: summary | attribute
            attribute: fast-search
            rank: filter
        }
        field rating type float {
            indexing: summary | attribute
        }
        field review_count type int {
            indexing: summary | attribute
        }
        field created_at type long {
            indexing: summary | attribute
            attribute: fast-search
        }
        field image_url type uri {
            indexing: summary
        }
        field embedding type tensor<float>(x[384]) {
            indexing: summary | attribute
            attribute {
                distance-metric: prenormalized-angular
            }
            index {
                hnsw {
                    max-links-per-node: 16
                    neighbors-to-explore-at-insert: 200
                }
            }
        }
        field attributes type map<string, string> {
            indexing: summary
            struct-field key   { indexing: attribute  match: exact }
            struct-field value { indexing: attribute }
        }
    }
    fieldset default {
        fields: title, description
    }
    rank-profile default {
        first-phase {
            expression: nativeRank(title) + nativeRank(description)
        }
    }
    rank-profile bm25_ranking inherits default {
        first-phase {
            expression: bm25(title) * 3 + bm25(description)
        }
    }
    rank-profile semantic inherits default {
        inputs {
            query(query_embedding) tensor<float>(x[384])
        }
        first-phase {
            expression: closeness(field, embedding)
        }
    }
    rank-profile hybrid inherits default {
        inputs {
            query(query_embedding) tensor<float>(x[384])
            query(text_weight) double: 0.6
            query(semantic_weight) double: 0.4
        }
        function text_score() {
            expression: bm25(title) * 3 + bm25(description)
        }
        function semantic_score() {
            expression: closeness(field, embedding)
        }
        first-phase {
            expression: text_score
        }
        second-phase {
            expression {
                query(text_weight) * normalize_linear(text_score) +
                query(semantic_weight) * normalize_linear(semantic_score)
            }
            rerank-count: 200
        }
        match-features {
            bm25(title)
            bm25(description)
            closeness(field, embedding)
        }
    }
    rank-profile personalized inherits hybrid {
        inputs {
            query(query_embedding) tensor<float>(x[384])
            query(text_weight) double: 0.4
            query(semantic_weight) double: 0.3
            query(freshness_weight) double: 0.15
            query(popularity_weight) double: 0.15
        }
        function freshness_score() {
            expression: freshness(created_at)
        }
        function popularity() {
            expression: if(review_count > 0, log10(review_count) * attribute(rating), 0)
        }
        second-phase {
            expression {
                query(text_weight) * normalize_linear(text_score) +
                query(semantic_weight) * normalize_linear(semantic_score) +
                query(freshness_weight) * freshness_score +
                query(popularity_weight) * normalize_linear(popularity)
            }
            rerank-count: 300
        }
    }
}
```
