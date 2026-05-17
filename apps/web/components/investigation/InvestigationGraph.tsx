"use client";

/**
 * InvestigationGraph — central panel.
 *
 * The S-12 spec asks for a cosmos.gl wrapper (`@cosmograph/react`) with a
 * fallback to `react-force-graph-2d`. Neither is installed in this worktree
 * (no GPU dep budget yet), so this implementation runs a small self-contained
 * SVG force simulation that matches the same visual contract:
 *
 *   - Node color from `entity.semantic` (declared / discovered / ambiguous /
 *     suspicious / conflict / verified).
 *   - Edge stroke width scales with `confidence`.
 *   - Mount uses a spring-style relaxation (skipped on prefers-reduced-motion).
 *   - Conflict nodes pulse red via `animate-conflict-pulse`.
 *   - Click → `onNodeClick(entity_id)`.
 *
 * Swap to cosmos.gl by replacing the `<svg>` simulation block with
 * `<Cosmograph nodes={…} links={…} />` — props are already shaped to fit.
 */

import * as React from "react";
import { Filter, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import type { GraphEdge, GraphEntity, GraphSemantic } from "@/lib/mockInvestigationState";
import { cn } from "@/lib/utils";

export interface InvestigationGraphProps {
  entities: GraphEntity[];
  edges: GraphEdge[];
  onNodeClick?: (entityId: string) => void;
  /** Optional date filter (start/end ISO). Edges outside the range are dimmed. */
  filterRange?: { start: string | null; end: string | null };
  /**
   * Optional upper-bound timestamp. Edges with `occurred_at > currentTime` are
   * hidden. Used by the TimelineScrubber to animate the graph back through
   * time without disturbing existing filter state.
   */
  currentTime?: Date | null;
  className?: string;
}

const SEMANTIC_COLOR: Record<GraphSemantic, string> = {
  declared: "var(--color-declared)",
  discovered: "var(--color-discovered)",
  ambiguous: "var(--color-ambiguous)",
  suspicious: "var(--color-suspicious)",
  conflict: "var(--color-conflict)",
  verified: "var(--color-verified)",
};

const SEMANTIC_LABEL: Record<GraphSemantic, string> = {
  declared: "Declarado",
  discovered: "Descubierto",
  ambiguous: "Ambiguo",
  suspicious: "Sospechoso",
  conflict: "Conflicto",
  verified: "Verificado",
};

interface NodePos {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

export function InvestigationGraph({
  entities,
  edges,
  onNodeClick,
  currentTime,
  className,
}: InvestigationGraphProps) {
  const containerRef = React.useRef<HTMLDivElement | null>(null);
  const [size, setSize] = React.useState({ width: 600, height: 400 });
  const prefersReducedMotion = usePrefersReducedMotion();
  const [filtersOpen, setFiltersOpen] = React.useState(false);

  // Filters
  const [redOnly, setRedOnly] = React.useState(false);
  const [minWeight, setMinWeight] = React.useState(0);
  const minDate = edges.reduce<string | null>(
    (acc, e) => (e.occurred_at && (!acc || e.occurred_at < acc) ? e.occurred_at : acc),
    null,
  );
  const maxDate = edges.reduce<string | null>(
    (acc, e) => (e.occurred_at && (!acc || e.occurred_at > acc) ? e.occurred_at : acc),
    null,
  );
  const [fromDate, setFromDate] = React.useState<string | null>(minDate);
  const [toDate, setToDate] = React.useState<string | null>(maxDate);

  // Container size
  React.useEffect(() => {
    const el = containerRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => {
      const r = el.getBoundingClientRect();
      setSize({ width: Math.max(320, r.width), height: Math.max(280, r.height) });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Positions — one entry per entity id. Initialized on a circle around center
  // so the first frame is already coherent and the simulation has gradient to
  // descend.
  const positionsRef = React.useRef<Map<string, NodePos>>(new Map());
  const [, forceRender] = React.useReducer((x) => x + 1, 0);

  // Initialize / re-seed positions whenever the entity set changes.
  React.useLayoutEffect(() => {
    const positions = new Map<string, NodePos>();
    const cx = size.width / 2;
    const cy = size.height / 2;
    const radius = Math.min(size.width, size.height) * 0.35;
    entities.forEach((e, i) => {
      const existing = positionsRef.current.get(e.id);
      if (existing) {
        positions.set(e.id, existing);
        return;
      }
      if (typeof e.x === "number" && typeof e.y === "number") {
        positions.set(e.id, { x: e.x, y: e.y, vx: 0, vy: 0 });
        return;
      }
      const angle = (i / Math.max(1, entities.length)) * Math.PI * 2;
      positions.set(e.id, {
        x: cx + Math.cos(angle) * radius,
        y: cy + Math.sin(angle) * radius,
        vx: 0,
        vy: 0,
      });
    });
    positionsRef.current = positions;
    forceRender();
  }, [entities, size.width, size.height]);

  // Force simulation — Hooke springs along edges, mild Coulomb repulsion
  // between all pairs, centering force, velocity damping. Runs ~120 iterations
  // for the spring mount; instant settle when reduced-motion is on.
  React.useEffect(() => {
    const positions = positionsRef.current;
    if (positions.size === 0) return;

    const iterations = prefersReducedMotion ? 220 : 220;
    const renderEvery = prefersReducedMotion ? iterations : 4;

    let raf = 0;
    let i = 0;

    const step = () => {
      tickForces(positions, entities, edges, size);
      i++;
      if (i % renderEvery === 0) forceRender();
      if (i < iterations) {
        if (prefersReducedMotion) {
          step();
        } else {
          raf = requestAnimationFrame(step);
        }
      } else {
        forceRender();
      }
    };

    if (prefersReducedMotion) {
      step();
    } else {
      raf = requestAnimationFrame(step);
    }
    return () => cancelAnimationFrame(raf);
    // intentionally exclude entities/edges/size — re-running only on prefers
    // toggle keeps positions stable between filter clicks.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefersReducedMotion]);

  // Filter view (does not affect simulation — keeps layout stable while user
  // toggles filters).
  const currentTimeIso = currentTime ? currentTime.toISOString() : null;
  const visibleEdges = edges.filter((e) => {
    if (redOnly && !["suspicious", "conflict"].includes(e.semantic)) return false;
    if (e.weight < minWeight) return false;
    if (fromDate && e.occurred_at && e.occurred_at < fromDate) return false;
    if (toDate && e.occurred_at && e.occurred_at > toDate) return false;
    if (currentTimeIso && e.occurred_at && e.occurred_at > currentTimeIso) return false;
    return true;
  });

  return (
    <section
      aria-label="Mapa de relaciones"
      className={cn(
        "relative flex h-full min-h-0 flex-col overflow-hidden rounded-[var(--radius-lg)] border bg-[var(--color-canvas)]",
        className,
      )}
    >
      <header className="flex items-center justify-between border-b border-[var(--color-border-default)] bg-[var(--color-surface)] px-4 py-3">
        <h2 className="font-display text-lg">Mapa de relaciones</h2>
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
            {entities.length} nodos · {visibleEdges.length}/{edges.length} aristas
          </span>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setFiltersOpen((v) => !v)}
            aria-pressed={filtersOpen}
            aria-label="Mostrar filtros"
          >
            <Filter className="h-3.5 w-3.5" aria-hidden />
            <span className="ml-1">Filtros</span>
          </Button>
        </div>
      </header>

      <div ref={containerRef} className="relative min-h-0 flex-1">
        <svg
          width={size.width}
          height={size.height}
          viewBox={`0 0 ${size.width} ${size.height}`}
          className="block h-full w-full"
          role="img"
          aria-label="Grafo de entidades cruzadas"
        >
          {/* Edges */}
          <g>
            {visibleEdges.map((edge) => {
              const a = positionsRef.current.get(edge.from);
              const b = positionsRef.current.get(edge.to);
              if (!a || !b) return null;
              const color = SEMANTIC_COLOR[edge.semantic];
              const width = 0.5 + edge.confidence * 3;
              return (
                <line
                  key={edge.id}
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke={color}
                  strokeWidth={width}
                  strokeOpacity={0.55}
                  className={edge.semantic === "conflict" ? "animate-conflict-pulse" : undefined}
                />
              );
            })}
          </g>

          {/* Nodes */}
          <g>
            {entities.map((e) => {
              const p = positionsRef.current.get(e.id);
              if (!p) return null;
              const color = SEMANTIC_COLOR[e.semantic];
              const r = e.type === "person" ? 11 : e.type === "company" ? 9 : 8;
              return (
                <NodeGlyph
                  key={e.id}
                  entity={e}
                  x={p.x}
                  y={p.y}
                  r={r}
                  color={color}
                  onClick={onNodeClick}
                />
              );
            })}
          </g>
        </svg>

        {/* Legend */}
        <ul className="pointer-events-none absolute bottom-2 left-2 flex flex-wrap gap-1.5 text-[10px]">
          {(Object.keys(SEMANTIC_COLOR) as GraphSemantic[]).map((s) => (
            <li
              key={s}
              className="inline-flex items-center gap-1 rounded-full bg-[var(--color-surface)]/85 px-2 py-0.5 font-mono backdrop-blur"
              style={{ color: SEMANTIC_COLOR[s] }}
            >
              <span
                aria-hidden
                className="h-1.5 w-1.5 rounded-full"
                style={{ backgroundColor: SEMANTIC_COLOR[s] }}
              />
              {SEMANTIC_LABEL[s]}
            </li>
          ))}
        </ul>

        {/* Filters drawer */}
        {filtersOpen ? (
          <aside
            aria-label="Filtros del grafo"
            className="absolute top-2 right-2 w-64 rounded-[var(--radius-md)] border bg-[var(--color-surface)] p-3 text-xs shadow-lg"
          >
            <header className="mb-2 flex items-center justify-between">
              <span className="font-mono text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
                Filtros
              </span>
              <button
                type="button"
                onClick={() => setFiltersOpen(false)}
                className="rounded-sm p-1 hover:bg-[var(--color-surface-2)]"
                aria-label="Cerrar filtros"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </header>

            <label className="mb-3 flex cursor-pointer items-center justify-between gap-2">
              <span>Solo aristas rojas</span>
              <input
                type="checkbox"
                checked={redOnly}
                onChange={(e) => setRedOnly(e.target.checked)}
                aria-label="Mostrar solo aristas rojas"
              />
            </label>

            <label className="mb-3 block">
              <span className="mb-1 block font-mono text-[10px] uppercase text-[var(--color-text-muted)]">
                Peso mínimo: {minWeight.toFixed(2)}
              </span>
              <input
                type="range"
                min={0}
                max={2}
                step={0.1}
                value={minWeight}
                onChange={(e) => setMinWeight(Number(e.target.value))}
                className="w-full"
                aria-label="Peso mínimo"
              />
            </label>

            <label className="mb-2 block">
              <span className="mb-1 block font-mono text-[10px] uppercase text-[var(--color-text-muted)]">
                Desde
              </span>
              <input
                type="date"
                value={fromDate?.slice(0, 10) ?? ""}
                onChange={(e) => setFromDate(e.target.value || null)}
                className="w-full rounded-[var(--radius-sm)] border bg-[var(--color-surface-2)] px-2 py-1"
              />
            </label>
            <label className="mb-2 block">
              <span className="mb-1 block font-mono text-[10px] uppercase text-[var(--color-text-muted)]">
                Hasta
              </span>
              <input
                type="date"
                value={toDate?.slice(0, 10) ?? ""}
                onChange={(e) => setToDate(e.target.value || null)}
                className="w-full rounded-[var(--radius-sm)] border bg-[var(--color-surface-2)] px-2 py-1"
              />
            </label>
          </aside>
        ) : null}
      </div>
    </section>
  );
}

function NodeGlyph({
  entity,
  x,
  y,
  r,
  color,
  onClick,
}: {
  entity: GraphEntity;
  x: number;
  y: number;
  r: number;
  color: string;
  onClick?: (id: string) => void;
}) {
  return (
    <g
      transform={`translate(${x},${y})`}
      tabIndex={0}
      role="button"
      aria-label={`${entity.name} — ${entity.type}`}
      className={cn(
        "cursor-pointer outline-none focus-visible:[outline:2px_solid_var(--color-accent)]",
      )}
      onClick={() => onClick?.(entity.id)}
      onKeyDown={(ev) => {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          onClick?.(entity.id);
        }
      }}
    >
      <circle
        r={r + 4}
        fill={color}
        opacity={0.15}
        className={entity.semantic === "conflict" ? "animate-conflict-pulse" : undefined}
      />
      <circle
        r={r}
        fill={color}
        stroke="var(--color-canvas)"
        strokeWidth={1.5}
      />
      <text
        y={r + 12}
        textAnchor="middle"
        className="pointer-events-none fill-[var(--color-text-primary)] font-mono"
        fontSize={10}
      >
        {truncate(entity.name, 26)}
      </text>
    </g>
  );
}

function truncate(s: string, n: number): string {
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}

// ─────────────────────────────────────────────────────────────────────────────
// Force simulation step
// ─────────────────────────────────────────────────────────────────────────────

function tickForces(
  positions: Map<string, NodePos>,
  entities: GraphEntity[],
  edges: GraphEdge[],
  size: { width: number; height: number },
) {
  const cx = size.width / 2;
  const cy = size.height / 2;
  const ids = entities.map((e) => e.id);

  // Coulomb-ish repulsion between pairs.
  const REPULSION = 1800;
  for (let i = 0; i < ids.length; i++) {
    const a = positions.get(ids[i]);
    if (!a) continue;
    for (let j = i + 1; j < ids.length; j++) {
      const b = positions.get(ids[j]);
      if (!b) continue;
      const dx = a.x - b.x;
      const dy = a.y - b.y;
      const distSq = Math.max(80, dx * dx + dy * dy);
      const force = REPULSION / distSq;
      const dist = Math.sqrt(distSq);
      const ux = dx / dist;
      const uy = dy / dist;
      a.vx += ux * force;
      a.vy += uy * force;
      b.vx -= ux * force;
      b.vy -= uy * force;
    }
  }

  // Hooke springs along edges (rest length depends on edge weight).
  for (const edge of edges) {
    const a = positions.get(edge.from);
    const b = positions.get(edge.to);
    if (!a || !b) continue;
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
    const rest = 110 + 40 / Math.max(0.2, edge.weight);
    const k = 0.03 * (0.5 + edge.confidence);
    const f = (dist - rest) * k;
    const ux = dx / dist;
    const uy = dy / dist;
    a.vx += ux * f;
    a.vy += uy * f;
    b.vx -= ux * f;
    b.vy -= uy * f;
  }

  // Centering.
  const CENTER_FORCE = 0.012;
  for (const id of ids) {
    const p = positions.get(id);
    if (!p) continue;
    p.vx += (cx - p.x) * CENTER_FORCE;
    p.vy += (cy - p.y) * CENTER_FORCE;
  }

  // Damping + integrate.
  const DAMPING = 0.78;
  const padding = 24;
  for (const id of ids) {
    const p = positions.get(id);
    if (!p) continue;
    p.vx *= DAMPING;
    p.vy *= DAMPING;
    p.x += p.vx;
    p.y += p.vy;
    if (p.x < padding) p.x = padding;
    if (p.y < padding) p.y = padding;
    if (p.x > size.width - padding) p.x = size.width - padding;
    if (p.y > size.height - padding) p.y = size.height - padding;
  }
}
