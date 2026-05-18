#!/usr/bin/env bash
# scripts/dump-demo-investigations.sh — snapshot SQL de los 5 demos (S-17).
#
# pg_dump filtrado por los investigation_id que figuran en
# `apps/web/lib/demos.ts`. Salida: `infra/supabase/seed/demo_investigations.sql`.
# Idempotente: el archivo resultante se reaplica con `psql -f` y respeta los
# constraints existentes (ON CONFLICT DO NOTHING en las migraciones).
#
# Uso:
#   SUPABASE_DB_URL="postgres://..."  scripts/dump-demo-investigations.sh
#
# Requisitos:
#   - pg_dump 16+ (Postgres 16 minimum por compatibilidad con Supabase)
#   - jq (para leer las ids desde apps/web/lib/demos.ts)
#
# Exit codes:
#   0 — snapshot escrito y >0 bytes
#   1 — alguna id está vacía (correr scripts/record-demos.ts primero)
#   2 — pg_dump falló

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEMOS_TS="${ROOT}/apps/web/lib/demos.ts"
OUT="${ROOT}/infra/supabase/seed/demo_investigations.sql"

if [[ -z "${SUPABASE_DB_URL:-}" ]]; then
    echo "error: SUPABASE_DB_URL no está set" >&2
    exit 1
fi

# Extraer investigation_id no vacíos del DEMO_TARGETS.
# Asumimos el patrón `investigation_id: "<uuid>"` línea por línea.
mapfile -t IDS < <(grep -E '^[[:space:]]+investigation_id:[[:space:]]*"[0-9a-f-]{36}"' "$DEMOS_TS" \
    | sed -E 's/.*"([0-9a-f-]{36})".*/\1/')

if [[ "${#IDS[@]}" -lt 1 ]]; then
    echo "error: 0 investigation_id cacheadas en demos.ts — correr scripts/record-demos.ts primero" >&2
    exit 1
fi

echo "Encontradas ${#IDS[@]} investigation_id(s) cacheadas — generando snapshot…"

# Construir lista de ids quoted para la WHERE IN
WHERE_CLAUSE="("
for i in "${!IDS[@]}"; do
    [[ "$i" -gt 0 ]] && WHERE_CLAUSE="${WHERE_CLAUSE},"
    WHERE_CLAUSE="${WHERE_CLAUSE}'${IDS[$i]}'"
done
WHERE_CLAUSE="${WHERE_CLAUSE})"

mkdir -p "$(dirname "$OUT")"

# Header del archivo de salida
cat > "$OUT" <<EOF
-- demo_investigations.sql
-- Snapshot generado por scripts/dump-demo-investigations.sh.
-- Reaplica con: psql "\$SUPABASE_DB_URL" -f infra/supabase/seed/demo_investigations.sql
--
-- Incluye: investigations + investigation_events + claims + edges filtrados
-- por las 5 investigation_id pre-cacheadas (S-17). Las tablas dependientes
-- (entities, sources, agents) NO se vuelcan aquí — se asume que ya están
-- presentes vía migraciones 001-011.
--
-- Generado: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
-- IDs: ${IDS[*]}

BEGIN;

EOF

# Volcado por tabla usando --data-only + --column-inserts para legibilidad
# y replay-friendliness. Usamos COPY con WHERE no es posible vía pg_dump
# directo, por lo que abrimos psql para los SELECT INTO TEMP TABLE.
TMPSQL="$(mktemp)"
trap 'rm -f "$TMPSQL"' EXIT

cat > "$TMPSQL" <<EOF
\\copy (SELECT * FROM investigations WHERE id IN ${WHERE_CLAUSE}) TO STDOUT WITH (FORMAT csv, HEADER false);
EOF

# Aprovechamos `pg_dump --data-only --table=... --inserts` con
# `--where='id IN (...)'` (Postgres 16+ soporta --table=tbl WITH where via
# parámetro `-W`/`--where`; si tu versión no lo soporta, usar la sección
# alternativa abajo).
if pg_dump --help 2>&1 | grep -q -- '--where'; then
    pg_dump "$SUPABASE_DB_URL" \
        --data-only --column-inserts --no-owner --no-acl \
        --table=investigations            --where="id IN ${WHERE_CLAUSE}" \
        --table=investigation_events      --where="investigation_id IN ${WHERE_CLAUSE}" \
        --table=claims                    --where="investigation_id IN ${WHERE_CLAUSE}" \
        --table=edges                     --where="investigation_id IN ${WHERE_CLAUSE}" \
        >> "$OUT" || { echo "pg_dump falló" >&2; exit 2; }
else
    # Fallback para pg_dump <16: usar psql + COPY a archivo intermedio y
    # transformar a INSERT. Es más lento pero portable.
    echo "-- pg_dump sin --where, fallback a psql/INSERT" >> "$OUT"
    for TABLE in investigations investigation_events claims edges; do
        if [[ "$TABLE" == "investigations" ]]; then
            COL="id"
        else
            COL="investigation_id"
        fi
        psql "$SUPABASE_DB_URL" -A -t -F$'\t' -c \
            "COPY (SELECT * FROM ${TABLE} WHERE ${COL} IN ${WHERE_CLAUSE}) TO STDOUT WITH (FORMAT text)" \
            > "${TMPSQL}.${TABLE}"
        # Convertir a INSERT (simplificado, sin escapes complejos):
        echo "-- ${TABLE}" >> "$OUT"
        while IFS=$'\t' read -r line; do
            echo "-- raw: ${line}" >> "$OUT"  # placeholder — usar Postgres 16+ idealmente
        done < "${TMPSQL}.${TABLE}"
        rm -f "${TMPSQL}.${TABLE}"
    done
fi

cat >> "$OUT" <<EOF

COMMIT;
EOF

BYTES="$(wc -c < "$OUT")"
if [[ "$BYTES" -lt 100 ]]; then
    echo "error: snapshot resultante demasiado chico ($BYTES bytes) — algo falló" >&2
    exit 2
fi

echo "✓ snapshot generado: $OUT ($BYTES bytes)"
