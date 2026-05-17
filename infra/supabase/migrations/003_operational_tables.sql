-- 003_operational_tables.sql
-- Tablas operacionales: investigations, investigation_events, tool_cache, subscriptions.
--
-- Cierra los FKs pendientes desde 002:
--   - claims.investigation_id  → investigations(id)
--   - edges.investigation_id   → investigations(id)
--
-- investigation_events.id es BIGSERIAL: el SSE endpoint lo usa como Last-Event-ID
-- para reconexión (S-08). El orden de emisión queda monotónicamente creciente.

-- ---------------------------------------------------------------------------
-- investigations
-- ---------------------------------------------------------------------------
CREATE TABLE investigations (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    target_entity_id  UUID NOT NULL REFERENCES entities(id),
    country           CHAR(2) NOT NULL CHECK (country IN ('pe','cl','mx','sv')),
    locale            TEXT NOT NULL DEFAULT 'es',
    status            TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
                         'pending','planning','running','verifying',
                         'synthesizing','complete','failed','cancelled'
                      )),
    plan              JSONB NOT NULL DEFAULT '[]',
    dossier_md        TEXT,
    cost_usd          NUMERIC(8,4) NOT NULL DEFAULT 0,
    token_usage       JSONB NOT NULL DEFAULT '{}',
    progress_pct      SMALLINT NOT NULL DEFAULT 0 CHECK (progress_pct BETWEEN 0 AND 100),
    user_id           UUID,                            -- NULL = anónima
    is_public         BOOLEAN NOT NULL DEFAULT TRUE,
    started_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at       TIMESTAMPTZ,
    error_message     TEXT
);

-- ---------------------------------------------------------------------------
-- investigation_events
-- id BIGSERIAL → soporta header Last-Event-ID al reconectar el SSE
-- ---------------------------------------------------------------------------
CREATE TABLE investigation_events (
    id                BIGSERIAL PRIMARY KEY,
    investigation_id  UUID NOT NULL REFERENCES investigations(id),
    type              TEXT NOT NULL,                   -- agent_started, tool_call,
                                                      -- claim_created, edge_discovered,
                                                      -- verification_done,
                                                      -- investigation_complete, ...
    agent_callsign    TEXT,
    payload           JSONB NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- tool_cache
-- pg_cron schedule del cleanup vive en 005_triggers.sql.
-- ---------------------------------------------------------------------------
CREATE TABLE tool_cache (
    key         TEXT PRIMARY KEY,
    value       JSONB NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL
);

-- ---------------------------------------------------------------------------
-- subscriptions
-- ---------------------------------------------------------------------------
CREATE TABLE subscriptions (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL,                         -- auth.users.id (Supabase)
    entity_id   UUID NOT NULL REFERENCES entities(id),
    channels    JSONB NOT NULL,                        -- {"whatsapp": "...", "email": "..."}
    triggers    JSONB NOT NULL DEFAULT '["new_claim","conflict_detected"]',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, entity_id)
);

-- ---------------------------------------------------------------------------
-- Cerrar FKs hacia investigations (definidos sin constraint en 002).
-- ---------------------------------------------------------------------------
ALTER TABLE claims
    ADD CONSTRAINT claims_investigation_id_fkey
    FOREIGN KEY (investigation_id) REFERENCES investigations(id);

ALTER TABLE edges
    ADD CONSTRAINT edges_investigation_id_fkey
    FOREIGN KEY (investigation_id) REFERENCES investigations(id);
