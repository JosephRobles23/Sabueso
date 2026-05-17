-- 007_seed.sql
-- Seed mínimo para humo / E2E: 1 entity + 1 source + 1 claim.
--
-- Entity demo: Dina Boluarte (presidenta del Perú al momento del hack@latam).
-- Casos de uso del seed:
--   * Probar búsqueda trigram: `SELECT name FROM entities WHERE name % 'Boluart';`
--   * Probar search_vector: `SELECT name FROM entities
--                            WHERE search_vector @@ to_tsquery('spanish','boluarte');`
--   * Cualquier dashboard/staging tiene al menos una fila para verificar shapes.
--
-- UUIDs fijos: facilitan referencias estables desde fixtures de test y rehacer
-- joins manuales. ON CONFLICT DO NOTHING permite re-aplicar el seed en dev
-- sin chocar con los UNIQUE constraints.

-- ---------------------------------------------------------------------------
-- entity demo
-- ---------------------------------------------------------------------------
INSERT INTO entities (id, country, type, identifier, name, aliases, metadata)
VALUES (
    '11111111-1111-1111-1111-111111111111',
    'pe',
    'person',
    '47865836',                                       -- DNI público
    'Dina Ercilia Boluarte Zegarra',
    ARRAY['Dina Boluarte', 'Boluarte'],
    jsonb_build_object(
        'role', 'Presidenta de la República del Perú',
        'demo', true
    )
)
ON CONFLICT (country, type, identifier) DO NOTHING;

-- ---------------------------------------------------------------------------
-- source demo
-- ---------------------------------------------------------------------------
INSERT INTO sources (id, url, source_type, title, country)
VALUES (
    '22222222-2222-2222-2222-222222222222',
    'https://www.gob.pe/institucion/presidencia/funcionarios/dina-boluarte',
    'press',
    'Ficha oficial — Presidencia de la República (gob.pe)',
    'pe'
)
ON CONFLICT (url, snapshot_at) DO NOTHING;

-- ---------------------------------------------------------------------------
-- claim demo
-- predicate=holds_office, sin investigation_id (claim "fundacional" del seed)
-- ---------------------------------------------------------------------------
INSERT INTO claims (
    id, entity_id, predicate, object_value, source_id,
    source_extract, confidence, agent_callsign
)
VALUES (
    '33333333-3333-3333-3333-333333333333',
    '11111111-1111-1111-1111-111111111111',
    'holds_office',
    jsonb_build_object(
        'office', 'Presidenta de la República',
        'country', 'pe',
        'since', '2022-12-07'
    ),
    '22222222-2222-2222-2222-222222222222',
    'Asume la Presidencia tras la vacancia de Pedro Castillo el 7 de diciembre de 2022.',
    1.0,
    'seed'
)
ON CONFLICT (id) DO NOTHING;
