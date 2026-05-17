-- 008_pipeline_data.sql
-- Soporte para los flows de ingesta (S-15): legalize-pe, SEACE, JNE PDFs.
--
-- Cambios:
--   1. Amplía entities.type para aceptar 'law' (normas legalize-pe).
--   2. Crea pipeline_checkpoints — tracking incremental de la ingesta.
--      No es un mecanismo de "exactly once" formal; es el cursor de cada
--      flow para saber qué ya procesó y poder reanudar tras un crash.

-- ---------------------------------------------------------------------------
-- entities.type CHECK constraint: agregar 'law'
-- ---------------------------------------------------------------------------
ALTER TABLE entities DROP CONSTRAINT IF EXISTS entities_type_check;
ALTER TABLE entities ADD CONSTRAINT entities_type_check
    CHECK (type IN ('person','company','government_entity','contract','law'));

-- ---------------------------------------------------------------------------
-- pipeline_checkpoints
--   flow_id        — identificador estable del flow (ej. 'pe_legalize')
--   external_id    — cursor por elemento procesado (law_id, OCID, candidate id)
--   status         — 'ok' | 'failed' | 'skipped'
--   error          — mensaje de error si status='failed'
--   metadata       — extras (hash, byte size, etc) para debugging
--
-- (flow_id, external_id) es UNIQUE: vuelta a correr el flow no duplica trabajo.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pipeline_checkpoints (
    id             BIGSERIAL PRIMARY KEY,
    flow_id        TEXT NOT NULL,
    external_id    TEXT NOT NULL,
    status         TEXT NOT NULL CHECK (status IN ('ok','failed','skipped')),
    error          TEXT,
    metadata       JSONB NOT NULL DEFAULT '{}',
    processed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (flow_id, external_id)
);

CREATE INDEX IF NOT EXISTS idx_pipeline_checkpoints_flow_status
    ON pipeline_checkpoints (flow_id, status);
