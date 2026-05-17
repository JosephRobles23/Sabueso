-- 011_rpc_compare.sql
-- RPC compare_entities(entity_ids UUID[]) — backend del /comparar (S-14).
--
-- Devuelve por entity 4 dimensiones de riesgo + un agregado, cada una con
-- score 0-100 y un indicador 0/1/2 (verde/ámbar/rojo) listo para pintar
-- 🟢🟡🔴 en el heatmap.
--
-- Definiciones de cada dimensión (mantener simples y derivables de
-- claims/edges sin tablas nuevas):
--
--   patrimony   = exceso de bienes descubiertos vs declarados.
--                 ((discovered_property) - (declared_property)) clamped a [0, ∞),
--                 multiplicado por 25, tope 100. 0 declarados ni descubiertos → 0.
--
--   contracts   = volumen de contratos en los que la entity está envuelta.
--                 count de edges con type='awarded_contract' tocando la entity,
--                 ×10, tope 100. No es per se "malo"; el frontend decide cómo
--                 narrar el color.
--
--   conflicts   = claims que el verificador o los investigadores marcaron como
--                 conflictos de interés / puerta giratoria / voto interesado.
--                 ×20, tope 100.
--
--   antecedents = claims sobre antecedentes penales, sentencias, denuncias,
--                 sanciones administrativas o remociones previas. ×25, tope 100.
--
--   aggregate   = promedio simple de las 4. Indicador idéntico al de los
--                 componentes (verde <33, ámbar <66, rojo ≥66).
--
-- Para la demo del hack@latam los pesos están parametrizados como literales:
-- ajustar acá si los investigadores producen más claims de los esperados y
-- alguno satura. Las thresholds del indicador viven en risk_indicator().

-- ---------------------------------------------------------------------------
-- risk_indicator(score) → 0|1|2  (verde|ámbar|rojo)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION risk_indicator(score INT)
RETURNS SMALLINT
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $$
    SELECT CASE
        WHEN score IS NULL  THEN 0::SMALLINT
        WHEN score >= 66    THEN 2::SMALLINT
        WHEN score >= 33    THEN 1::SMALLINT
        ELSE                     0::SMALLINT
    END;
$$;

-- ---------------------------------------------------------------------------
-- compare_entities(entity_ids UUID[])
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION compare_entities(p_entity_ids UUID[])
RETURNS TABLE (
    entity_id              UUID,
    patrimony_score        INT,
    patrimony_indicator    SMALLINT,
    contracts_score        INT,
    contracts_indicator    SMALLINT,
    conflicts_score        INT,
    conflicts_indicator    SMALLINT,
    antecedents_score      INT,
    antecedents_indicator  SMALLINT,
    aggregate_score        INT,
    aggregate_indicator    SMALLINT
)
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
    WITH ids AS (
        SELECT DISTINCT unnest(p_entity_ids) AS eid
    ),
    patrimony AS (
        SELECT
            i.eid,
            LEAST(
                100,
                GREATEST(
                    0,
                    COUNT(*) FILTER (WHERE c.predicate = 'discovered_property')
                    - COUNT(*) FILTER (WHERE c.predicate = 'declared_property')
                ) * 25
            )::INT AS score
        FROM ids i
        LEFT JOIN claims c
            ON c.entity_id = i.eid
           AND c.superseded_by IS NULL
        GROUP BY i.eid
    ),
    contracts AS (
        SELECT
            i.eid,
            LEAST(
                100,
                COUNT(*) FILTER (WHERE e.type = 'awarded_contract') * 10
            )::INT AS score
        FROM ids i
        LEFT JOIN edges e
            ON (e.from_entity = i.eid OR e.to_entity = i.eid)
        GROUP BY i.eid
    ),
    conflicts AS (
        SELECT
            i.eid,
            LEAST(
                100,
                COUNT(*) FILTER (
                    WHERE c.predicate IN (
                        'conflict_of_interest',
                        'voted_against_interest',
                        'revolving_door'
                    )
                ) * 20
            )::INT AS score
        FROM ids i
        LEFT JOIN claims c
            ON c.entity_id = i.eid
           AND c.superseded_by IS NULL
        GROUP BY i.eid
    ),
    antecedents AS (
        SELECT
            i.eid,
            LEAST(
                100,
                COUNT(*) FILTER (
                    WHERE c.predicate IN (
                        'criminal_record',
                        'sentencia',
                        'denuncia',
                        'sanction',
                        'prior_removal'
                    )
                ) * 25
            )::INT AS score
        FROM ids i
        LEFT JOIN claims c
            ON c.entity_id = i.eid
           AND c.superseded_by IS NULL
        GROUP BY i.eid
    ),
    combined AS (
        SELECT
            i.eid                       AS eid,
            COALESCE(p.score,  0)       AS p_score,
            COALESCE(ct.score, 0)       AS ct_score,
            COALESCE(cf.score, 0)       AS cf_score,
            COALESCE(an.score, 0)       AS an_score
        FROM ids i
        LEFT JOIN patrimony   p  ON p.eid  = i.eid
        LEFT JOIN contracts   ct ON ct.eid = i.eid
        LEFT JOIN conflicts   cf ON cf.eid = i.eid
        LEFT JOIN antecedents an ON an.eid = i.eid
    )
    SELECT
        c.eid                                                       AS entity_id,
        c.p_score                                                   AS patrimony_score,
        risk_indicator(c.p_score)                                   AS patrimony_indicator,
        c.ct_score                                                  AS contracts_score,
        risk_indicator(c.ct_score)                                  AS contracts_indicator,
        c.cf_score                                                  AS conflicts_score,
        risk_indicator(c.cf_score)                                  AS conflicts_indicator,
        c.an_score                                                  AS antecedents_score,
        risk_indicator(c.an_score)                                  AS antecedents_indicator,
        ((c.p_score + c.ct_score + c.cf_score + c.an_score) / 4)::INT
                                                                    AS aggregate_score,
        risk_indicator(
            ((c.p_score + c.ct_score + c.cf_score + c.an_score) / 4)::INT
        )                                                           AS aggregate_indicator
    FROM combined c;
$$;

-- El RPC se llama desde el cliente (PostgREST) con auth anon/authenticated.
-- Las entities son lectura pública en este schema, así que abrimos a todos.
GRANT EXECUTE ON FUNCTION compare_entities(UUID[]) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION risk_indicator(INT)      TO anon, authenticated, service_role;
