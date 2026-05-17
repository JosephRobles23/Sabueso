-- 002_core_tables.sql
-- Tablas del grafo de conocimiento: entities, sources, claims, edges.
--
-- Orden de creación:
--   1. entities  (sin FKs salientes)
--   2. sources   (sin FKs salientes)
--   3. claims    (referencia entities y sources; investigation_id queda como
--                 UUID sin FK; el constraint se agrega en 003 después de crear
--                 investigations para evitar dependencia circular entre migraciones)
--   4. edges     (referencia entities; investigation_id idem que claims)
--
-- Los índices viven en 004_indexes.sql.

-- ---------------------------------------------------------------------------
-- entities_search_vector(name, identifier, aliases) -> tsvector
--
-- Postgres considera `to_tsvector('spanish', ...)` como STABLE (resuelve la
-- regconfig vía catálogo), y eso es ilegal dentro de un `GENERATED ALWAYS AS
-- ... STORED`. Encapsulamos el cómputo en una función marcada IMMUTABLE para
-- desbloquear la generated column. Suposición: nunca se altera la text search
-- config 'spanish' en runtime (lo cual obligaría a re-bakeed los stored).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION entities_search_vector(
    p_name TEXT, p_identifier TEXT, p_aliases TEXT[]
)
RETURNS TSVECTOR
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $$
    SELECT setweight(to_tsvector('spanish'::regconfig, coalesce(p_name, '')), 'A')
        || setweight(to_tsvector('spanish'::regconfig, coalesce(p_identifier, '')), 'B')
        || setweight(
              to_tsvector('spanish'::regconfig,
                          array_to_string(coalesce(p_aliases, '{}'::text[]), ' ')),
              'C')
$$;

-- ---------------------------------------------------------------------------
-- entities
-- ---------------------------------------------------------------------------
CREATE TABLE entities (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    country         CHAR(2) NOT NULL CHECK (country IN ('pe','cl','mx','sv')),
    type            TEXT NOT NULL CHECK (type IN (
                       'person','company','government_entity','contract'
                    )),
    identifier      TEXT,                              -- DNI/RUC/CURP/RUT/DUI
    name            TEXT NOT NULL,
    aliases         TEXT[] NOT NULL DEFAULT '{}',
    metadata        JSONB NOT NULL DEFAULT '{}',
    embedding       VECTOR(1536),
    search_vector   TSVECTOR GENERATED ALWAYS AS (
                       entities_search_vector(name, identifier, aliases)
                    ) STORED,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (country, type, identifier)
);

-- ---------------------------------------------------------------------------
-- sources
-- ---------------------------------------------------------------------------
CREATE TABLE sources (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    url             TEXT NOT NULL,
    source_type     TEXT NOT NULL CHECK (source_type IN (
                       'legalize','seace','jne','sunarp','sunat','el_peruano',
                       'manolo','press','wayback','user_upload'
                    )),
    title           TEXT,
    snapshot_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    content_hash    TEXT,                              -- SHA-256 del snapshot
    content_storage TEXT,                              -- gs://bucket/path o NULL
    country         CHAR(2) CHECK (country IS NULL OR country IN ('pe','cl','mx','sv'))
);

-- ---------------------------------------------------------------------------
-- claims
-- investigation_id queda sin FK aquí; se agrega en 003 tras crear investigations.
-- ---------------------------------------------------------------------------
CREATE TABLE claims (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    investigation_id  UUID,
    entity_id         UUID NOT NULL REFERENCES entities(id),
    predicate         TEXT NOT NULL,
    object_value      JSONB NOT NULL,
    object_entity_id  UUID REFERENCES entities(id),
    source_id         UUID NOT NULL REFERENCES sources(id),
    source_extract    TEXT CHECK (source_extract IS NULL OR length(source_extract) <= 500),
    source_hash       TEXT,                            -- SHA-256 del contenido en snapshot
    confidence        FLOAT CHECK (confidence BETWEEN 0 AND 1),
    agent_callsign    TEXT NOT NULL,
    superseded_by     UUID REFERENCES claims(id),
    verified_by_jueza BOOLEAN NOT NULL DEFAULT FALSE,
    verified_at       TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- edges
-- investigation_id queda sin FK aquí; se agrega en 003 tras crear investigations.
-- ---------------------------------------------------------------------------
CREATE TABLE edges (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    investigation_id  UUID,
    from_entity       UUID NOT NULL REFERENCES entities(id),
    to_entity         UUID NOT NULL REFERENCES entities(id),
    type              TEXT NOT NULL,
    weight            FLOAT NOT NULL DEFAULT 1.0,
    confidence        FLOAT CHECK (confidence BETWEEN 0 AND 1),
    evidence_claims   UUID[] NOT NULL DEFAULT '{}',
    discovered_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    agent_callsign    TEXT,
    UNIQUE (from_entity, to_entity, type)
);
