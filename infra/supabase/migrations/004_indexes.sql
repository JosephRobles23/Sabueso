-- 004_indexes.sql
-- Índices del schema, agrupados por tabla. Separados de las migraciones de
-- creación para mantener legibilidad y permitir recrearlos sin tocar el DDL.
--
-- Tipos en uso:
--   GIN     : búsqueda full-text (tsvector) y similitud trigram (gin_trgm_ops)
--   ivfflat : ANN sobre embeddings pgvector (cosine)
--   BTREE   : FKs y filtros de rango / igualdad (default)
--   Parciales : indexan solo el subconjunto consultado caliente

-- ---------------------------------------------------------------------------
-- entities
-- ---------------------------------------------------------------------------
CREATE INDEX idx_entities_search        ON entities USING GIN (search_vector);
CREATE INDEX idx_entities_name_trgm     ON entities USING GIN (name gin_trgm_ops);
CREATE INDEX idx_entities_embedding     ON entities USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
CREATE INDEX idx_entities_country_type  ON entities (country, type);

-- ---------------------------------------------------------------------------
-- claims
-- ---------------------------------------------------------------------------
CREATE INDEX idx_claims_entity          ON claims (entity_id);
CREATE INDEX idx_claims_investigation   ON claims (investigation_id);
CREATE INDEX idx_claims_predicate       ON claims (predicate);
-- Parcial: solo los claims aún vigentes (no supercedidos) — set caliente para lecturas
CREATE INDEX idx_claims_not_superseded  ON claims (entity_id) WHERE superseded_by IS NULL;

-- ---------------------------------------------------------------------------
-- edges
-- ---------------------------------------------------------------------------
CREATE INDEX idx_edges_from             ON edges (from_entity);
CREATE INDEX idx_edges_to               ON edges (to_entity);
CREATE INDEX idx_edges_type             ON edges (type);

-- ---------------------------------------------------------------------------
-- investigations
-- ---------------------------------------------------------------------------
CREATE INDEX idx_investigations_target  ON investigations (target_entity_id);
CREATE INDEX idx_investigations_user    ON investigations (user_id) WHERE user_id IS NOT NULL;
CREATE INDEX idx_investigations_status  ON investigations (status);
-- Parcial: feed público "investigaciones recientes completas"
CREATE INDEX idx_investigations_public  ON investigations (is_public, finished_at DESC)
    WHERE is_public = TRUE AND status = 'complete';

-- ---------------------------------------------------------------------------
-- investigation_events
-- Compuesto (investigation_id, id): scan ordenado para replay desde Last-Event-ID
-- ---------------------------------------------------------------------------
CREATE INDEX idx_events_investigation_id ON investigation_events (investigation_id, id);

-- ---------------------------------------------------------------------------
-- sources
-- ---------------------------------------------------------------------------
CREATE UNIQUE INDEX uq_sources_url_snapshot ON sources (url, snapshot_at);

-- ---------------------------------------------------------------------------
-- tool_cache
-- ---------------------------------------------------------------------------
CREATE INDEX idx_tool_cache_expiry      ON tool_cache (expires_at);
