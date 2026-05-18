-- demo_investigations.sql
--
-- ⚠ ARCHIVO PLACEHOLDER ⚠
--
-- El snapshot real se genera con:
--     bash scripts/dump-demo-investigations.sh
-- después de haber corrido `pnpm tsx scripts/record-demos.ts` y haber
-- aceptado editorialmente las 5 investigaciones.
--
-- Mientras este archivo esté en estado placeholder, el LiveOrReplayToggle
-- mostrará los 5 demos como "pendiente de cachear" y no permitirá replay.
--
-- Restore una vez generado:
--     psql "$SUPABASE_DB_URL" -f infra/supabase/seed/demo_investigations.sql
--
-- Contenido esperado (post-dump):
--   - investigations (5 rows, una por DEMO_TARGET)
--   - investigation_events (cientos de rows con timestamps reales)
--   - claims (decenas de rows con confidence + source_url)
--   - edges (decenas de rows representando la red descubierta)
--
-- Todas las inserciones usan ON CONFLICT DO NOTHING para idempotencia.

-- Placeholder no-op transaction: el archivo se puede aplicar sin romper
-- nada (sólo log), pero no produce datos.
BEGIN;
DO $$ BEGIN
  RAISE NOTICE 'demo_investigations.sql placeholder — correr scripts/dump-demo-investigations.sh para llenar';
END $$;
COMMIT;
