-- 005_triggers.sql
-- Triggers + funciones auxiliares + jobs pg_cron.
--
-- Pieza crítica:
--   notify_investigation_event() es la base del canal SSE.
--   Cada INSERT en investigation_events emite NOTIFY sobre un canal cuyo
--   nombre deriva del investigation_id sanitizado (Postgres NOTIFY no acepta
--   guiones en identifiers sin quotearlos, así que sustituimos '-' por '_').
--
--   El payload de NOTIFY tiene límite de 8000 bytes; mandamos solo el ID y
--   metadatos mínimos. El consumidor (SSE endpoint, S-08) hace SELECT del row
--   completo y lo emite con id=<NEW.id> para soportar Last-Event-ID en reconexión.

-- ---------------------------------------------------------------------------
-- set_updated_at: trigger genérico para mantener `updated_at` al día.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_entities_set_updated_at
    BEFORE UPDATE ON entities
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- notify_investigation_event: emite NOTIFY al canal inv_<uuid-sanitizado>.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION notify_investigation_event()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    channel_name TEXT;
    payload      TEXT;
BEGIN
    -- NOTIFY no acepta '-' en el nombre del canal sin quoting; sanitizamos.
    channel_name := 'inv_' || replace(NEW.investigation_id::text, '-', '_');

    -- Payload compacto: el SSE consumer hace SELECT por id para el row completo.
    payload := json_build_object(
        'id',             NEW.id,
        'investigation',  NEW.investigation_id,
        'type',           NEW.type,
        'agent',          NEW.agent_callsign,
        'created_at',     NEW.created_at
    )::text;

    PERFORM pg_notify(channel_name, payload);
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_investigation_events_notify
    AFTER INSERT ON investigation_events
    FOR EACH ROW
    EXECUTE FUNCTION notify_investigation_event();

-- ---------------------------------------------------------------------------
-- pg_cron: limpieza horaria de tool_cache vencido.
-- ---------------------------------------------------------------------------
SELECT cron.schedule(
    'cleanup-tool-cache',
    '0 * * * *',
    $cleanup$ DELETE FROM tool_cache WHERE expires_at < now() $cleanup$
);
