---
name: search
description: Implementing search that works at scale: chooses between PostgreSQL full-text search and Elasticsearch based on requirements, builds tsvector indexes with the right language config, combines full-text with filter predicates, ranks results with ts_rank, adds fuzzy/trigram matching for typo tolerance, designs an Elasticsearch index with correct mappings and analyzers, and keeps the search index in sync with the source of truth. Use when you want to add search, implement full-text search, use PostgreSQL FTS, set up Elasticsearch, add fuzzy search, combine search with filters, rank search results, or keep a search index in sync.
---

## search

Pick the right backend first. Add the right index. Never implement search with `LIKE '%term%'`.

### 1. Choose the backend

| Requirement | PostgreSQL FTS | Elasticsearch |
|-------------|---------------|---------------|
| Data already in Postgres | ✅ | Needs sync pipeline |
| Simple keyword search | ✅ | Overkill |
| Multi-language stemming | ✅ | ✅ Better control |
| Typo tolerance (fuzzy) | ✅ pg_trgm | ✅ Built-in |
| Relevance tuning per field | Limited | ✅ |
| Faceted search / aggregations | Hard | ✅ |
| Billions of documents | ❌ | ✅ |
| Real-time autocomplete | Possible | ✅ Better |

**Default to PostgreSQL FTS** when your data is already in Postgres and you do not need
aggregations or advanced relevance tuning. Add Elasticsearch only when Postgres cannot
meet the requirements — it is significant operational overhead.

---

### 2. PostgreSQL full-text search — the right way

```sql
-- Never do this — scans every row, no index, slow at scale
SELECT * FROM products WHERE name LIKE '%wireless headphones%';

-- Full-text search with GIN index — fast, stemmed, ranked
```

**Step 1 — add a `tsvector` column and index:**

```sql
-- Add a generated tsvector column (PostgreSQL 12+)
ALTER TABLE products
  ADD COLUMN search_vector tsvector
  GENERATED ALWAYS AS (
    setweight(to_tsvector('english', coalesce(name, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(description, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(brand, '')), 'A')
  ) STORED;

-- GIN index on the tsvector column
CREATE INDEX idx_products_search ON products USING gin(search_vector);
```

**Step 2 — query with `tsquery` and rank:**

```sql
-- Basic search
SELECT id, name, ts_rank(search_vector, query) AS rank
FROM products, to_tsquery('english', 'wireless & headphones') query
WHERE search_vector @@ query
ORDER BY rank DESC
LIMIT 20;

-- Phrase search
SELECT id, name
FROM products
WHERE search_vector @@ phraseto_tsquery('english', 'wireless headphones');

-- Prefix search (for autocomplete)
SELECT id, name
FROM products
WHERE search_vector @@ to_tsquery('english', 'wireless:* & head:*');
```

```python
# repositories/product_repository.py
"""
repositories/product_repository.py
------------------------------------
Product search using PostgreSQL full-text search.

Depends on: lib/db.py, lib/logger.py
Used by:    services/search_service.py
"""

from lib.logger import get_logger

logger = get_logger(__name__)


async def search_products(
    query: str,
    filters: dict | None = None,
    limit: int = 20,
    cursor: str | None = None,
) -> list[dict]:
    if not query.strip():
        return []

    # Sanitise query — convert free text to tsquery safely
    # plainto_tsquery handles arbitrary user input without injection risk
    params: dict = {"query": query, "limit": limit}
    conditions = ["search_vector @@ plainto_tsquery('english', :query)"]

    # Combine FTS with structured filters
    if filters:
        if filters.get("category"):
            conditions.append("category = :category")
            params["category"] = filters["category"]
        if filters.get("max_price"):
            conditions.append("price_cents <= :max_price")
            params["max_price"] = filters["max_price"]

    where = " AND ".join(conditions)

    rows = await db.fetch_all(
        f"""
        SELECT
            id, name, price_cents, category,
            ts_rank(search_vector, plainto_tsquery('english', :query)) AS rank
        FROM products
        WHERE {where}
        ORDER BY rank DESC, id DESC
        LIMIT :limit
        """,
        params,
    )
    logger.info("Product search executed. query=%s results=%d", query[:50], len(rows))
    return [dict(r) for r in rows]
```

---

### 3. Fuzzy / trigram search — typo tolerance

```sql
-- Enable pg_trgm extension
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- GIN trigram index on name (for similarity and ILIKE acceleration)
CREATE INDEX idx_products_name_trgm ON products USING gin(name gin_trgm_ops);

-- Fuzzy match — returns results even with typos
SELECT id, name, similarity(name, 'wireles headphnes') AS sim
FROM products
WHERE similarity(name, 'wireles headphnes') > 0.3
ORDER BY sim DESC
LIMIT 20;
```

**Combine FTS + trigram for best results:**
```sql
-- Exact FTS match boosted, trigram fuzzy as fallback
SELECT id, name,
  CASE
    WHEN search_vector @@ plainto_tsquery('english', 'wireless headphones')
    THEN ts_rank(search_vector, plainto_tsquery('english', 'wireless headphones')) + 1.0
    ELSE similarity(name, 'wireless headphones')
  END AS combined_rank
FROM products
WHERE
  search_vector @@ plainto_tsquery('english', 'wireless headphones')
  OR similarity(name, 'wireless headphones') > 0.3
ORDER BY combined_rank DESC
LIMIT 20;
```

---

### 4. Elasticsearch — index design and sync

**Index mapping — define before indexing any documents:**

```python
# lib/es_client.py
"""
lib/es_client.py
-----------------
Elasticsearch index management and search helpers.

Depends on: elasticsearch-py, lib/logger.py
Used by:    services/search_service.py, workers/search_sync_worker.py
"""

from elasticsearch import AsyncElasticsearch
from lib.logger import get_logger

logger = get_logger(__name__)
es = AsyncElasticsearch([settings.elasticsearch_url])

PRODUCTS_INDEX = "products_v1"

PRODUCTS_MAPPING = {
    "settings": {
        "number_of_shards":   1,
        "number_of_replicas": 1,
        "analysis": {
            "analyzer": {
                "product_analyzer": {
                    "type":      "custom",
                    "tokenizer": "standard",
                    "filter":    ["lowercase", "asciifolding", "english_stemmer"],
                },
            },
            "filter": {
                "english_stemmer": {"type": "stemmer", "language": "english"},
            },
        },
    },
    "mappings": {
        "properties": {
            "name":        {"type": "text",    "analyzer": "product_analyzer", "boost": 3},
            "brand":       {"type": "text",    "analyzer": "product_analyzer", "boost": 2},
            "description": {"type": "text",    "analyzer": "product_analyzer"},
            "category":    {"type": "keyword"},   # exact match / facet
            "price_cents": {"type": "integer"},
            "tenant_id":   {"type": "keyword"},
            "updated_at":  {"type": "date"},
        }
    },
}


async def ensure_index() -> None:
    exists = await es.indices.exists(index=PRODUCTS_INDEX)
    if not exists:
        await es.indices.create(index=PRODUCTS_INDEX, body=PRODUCTS_MAPPING)
        logger.info("Elasticsearch index created. index=%s", PRODUCTS_INDEX)


async def search_products(
    query: str,
    tenant_id: str,
    category: str | None = None,
    max_price: int | None = None,
    page: int = 1,
    size: int = 20,
) -> dict:
    must_filters = [{"term": {"tenant_id": tenant_id}}]

    if category:
        must_filters.append({"term": {"category": category}})
    if max_price:
        must_filters.append({"range": {"price_cents": {"lte": max_price}}})

    body = {
        "query": {
            "bool": {
                "must": {
                    "multi_match": {
                        "query":  query,
                        "fields": ["name^3", "brand^2", "description"],
                        "fuzziness": "AUTO",   # typo tolerance built-in
                        "type":   "best_fields",
                    }
                },
                "filter": must_filters,
            }
        },
        "from": (page - 1) * size,
        "size": size,
    }

    response = await es.search(index=PRODUCTS_INDEX, body=body)
    hits = response["hits"]["hits"]
    total = response["hits"]["total"]["value"]

    logger.info("ES search completed. query=%s total=%d", query[:50], total)
    return {
        "items": [{"id": h["_id"], **h["_source"], "score": h["_score"]} for h in hits],
        "total": total,
        "page":  page,
        "size":  size,
    }
```

---

### 5. Keep the search index in sync

```python
# workers/search_sync_worker.py
"""
workers/search_sync_worker.py
------------------------------
Syncs product changes from PostgreSQL to Elasticsearch.
Triggered by the outbox pattern — listens for product.updated events.

Depends on: lib/es_client.py, repositories/product_repository.py
Used by:    queue consumer
"""

from lib.es_client import es, PRODUCTS_INDEX
from lib.logger import get_logger

logger = get_logger(__name__)


async def sync_product(product_id: int) -> None:
    product = await product_repo.find_by_id(product_id)
    if not product:
        # Product deleted — remove from index
        await es.delete(index=PRODUCTS_INDEX, id=str(product_id), ignore=[404])
        logger.info("Product removed from search index. product_id=%s", product_id)
        return

    await es.index(
        index=PRODUCTS_INDEX,
        id=str(product_id),
        document={
            "name":        product["name"],
            "brand":       product["brand"],
            "description": product["description"],
            "category":    product["category"],
            "price_cents": product["price_cents"],
            "tenant_id":   product["tenant_id"],
            "updated_at":  product["updated_at"].isoformat(),
        },
    )
    logger.info("Product synced to search index. product_id=%s", product_id)
```

---

### 6. Search anti-patterns to avoid

| Anti-pattern | Why it hurts | Fix |
|-------------|-------------|-----|
| `LIKE '%term%'` on large tables | Full table scan, no index | PostgreSQL FTS with GIN index |
| `ILIKE '%term%'` | Same — case-insensitive but still full scan | `pg_trgm` GIN index |
| Indexing everything in Elasticsearch | Index bloat, slow writes | Map only searchable fields; use `keyword` for filters |
| Syncing ES synchronously in the request | Latency spike on every write | Async via outbox/queue |
| Rebuilding the entire index on every deploy | Downtime for large corpora | Blue-green index alias swap |
| `wildcard` query on unanalysed fields in ES | Extremely slow | Use `match` with `fuzziness` instead |

### Rules

- Never use `LIKE '%term%'` — it cannot use a btree index and scans every row.
- Use `plainto_tsquery` for user input in PostgreSQL — it handles arbitrary text safely without injection.
- Weight fields in `tsvector` with `setweight` — name and brand should outrank description.
- In Elasticsearch, map filter fields as `keyword` and search fields as `text` — never mix them.
- Keep the search index eventually consistent via the outbox pattern — never sync in the request path.
- Test search quality with real queries from users, not synthetic ones. Relevance tuning without real data is guesswork.
