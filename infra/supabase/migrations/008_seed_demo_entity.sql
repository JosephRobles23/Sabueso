-- 008_seed_demo_entity.sql
-- Seed para el primer end-to-end (S-10).
--
-- La entity demo previa (Dina Boluarte, persona sin RUC) no permite
-- ejercitar la tool `search_seace_contracts`, que pide un RUC de 11
-- dígitos. Insertamos una government_entity con RUC público verificable:
-- el Ministerio de Salud del Perú (MINSA), RUC 20131373237. SEACE
-- registra cientos de contratos a su nombre, lo que da hallazgos reales
-- para que El Contador emita claims y se valide el flujo entero.
--
-- Idempotente: cada INSERT usa ON CONFLICT DO NOTHING contra los UNIQUE
-- constraints existentes, así re-aplicar el seed en dev / staging no
-- choca.

-- ---------------------------------------------------------------------------
-- entity demo: MINSA (Ministerio de Salud del Perú)
-- ---------------------------------------------------------------------------
INSERT INTO entities (id, country, type, identifier, name, aliases, metadata)
VALUES (
    '44444444-4444-4444-4444-444444444444',
    'pe',
    'government_entity',
    '20131373237',                                  -- RUC público (SUNAT)
    'Ministerio de Salud del Perú',
    ARRAY['MINSA', 'Ministerio de Salud', 'MINSA Perú'],
    jsonb_build_object(
        'sector', 'salud',
        'website', 'https://www.gob.pe/minsa',
        'demo', true,
        'use_case', 'smoke-test S-10: El Contador → search_seace_contracts'
    )
)
ON CONFLICT (country, type, identifier) DO NOTHING;

-- ---------------------------------------------------------------------------
-- source demo: ficha del portal gob.pe
-- ---------------------------------------------------------------------------
INSERT INTO sources (id, url, source_type, title, country)
VALUES (
    '55555555-5555-5555-5555-555555555555',
    'https://www.gob.pe/minsa',
    'press',
    'Portal institucional — Ministerio de Salud (gob.pe)',
    'pe'
)
ON CONFLICT (url, snapshot_at) DO NOTHING;

-- ---------------------------------------------------------------------------
-- claim demo: holds_office del MINSA (entidad pública vigente)
-- Sin investigation_id (claim "fundacional" del seed). Confidence 1.0:
-- el rol institucional del MINSA es público y verificable.
-- ---------------------------------------------------------------------------
INSERT INTO claims (
    id, entity_id, predicate, object_value, source_id,
    source_extract, confidence, agent_callsign
)
VALUES (
    '66666666-6666-6666-6666-666666666666',
    '44444444-4444-4444-4444-444444444444',
    'holds_office',
    jsonb_build_object(
        'office', 'Ministerio rector del sector Salud',
        'country', 'pe',
        'since', '1935-10-05',
        'ruc', '20131373237'
    ),
    '55555555-5555-5555-5555-555555555555',
    'El Ministerio de Salud del Perú es el órgano rector del Sector Salud, RUC 20131373237.',
    1.0,
    'seed'
)
ON CONFLICT (id) DO NOTHING;
