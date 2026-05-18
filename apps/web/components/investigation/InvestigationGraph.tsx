"use client";

import * as React from "react";
import { ZoomIn, ZoomOut, Maximize2 } from "lucide-react";

import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import type { GraphEdge, GraphEntity, GraphSemantic } from "@/lib/mockInvestigationState";
import { cn } from "@/lib/utils";

export interface InvestigationGraphProps {
  entities: GraphEntity[];
  edges: GraphEdge[];
  onNodeClick?: (entityId: string) => void;
  filterRange?: { start: string | null; end: string | null };
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
  pinned?: boolean;
}

interface DragState {
  entityId: string;
  offsetX: number;
  offsetY: number;
}

interface ViewTransform {
  x: number;
  y: number;
  scale: number;
}

export function InvestigationGraph({
  entities,
  edges,
  onNodeClick,
  currentTime,
  className,
}: InvestigationGraphProps) {
  const containerRef = React.useRef<HTMLDivElement | null>(null);
  const svgRef = React.useRef<SVGSVGElement | null>(null);
  const [size, setSize] = React.useState({ width: 600, height: 400 });
  const prefersReducedMotion = usePrefersReducedMotion();
  const [selectedNode, setSelectedNode] = React.useState<string | null>(null);
  const [hoveredNode, setHoveredNode] = React.useState<string | null>(null);
  const dragRef = React.useRef<DragState | null>(null);
  const [view, setView] = React.useState<ViewTransform>({ x: 0, y: 0, scale: 1 });
  const panRef = React.useRef<{ startX: number; startY: number; viewX: number; viewY: number } | null>(null);

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

  const positionsRef = React.useRef<Map<string, NodePos>>(new Map());
  const [, forceRender] = React.useReducer((x: number) => x + 1, 0);

  React.useLayoutEffect(() => {
    const positions = new Map<string, NodePos>();
    const cx = size.width / 2;
    const cy = size.height / 2;
    const radius = Math.min(size.width, size.height) * 0.32;
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
      const angle = (i / Math.max(1, entities.length)) * Math.PI * 2 - Math.PI / 2;
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

  // Force simulation
  const simulationRunning = React.useRef(true);
  React.useEffect(() => {
    const positions = positionsRef.current;
    if (positions.size === 0) return;
    simulationRunning.current = true;
    let raf = 0;
    let frame = 0;
    const step = () => {
      if (!simulationRunning.current) return;
      tickForces(positions, entities, edges, size);
      frame++;
      if (frame % 3 === 0) forceRender();
      if (frame < 300) {
        raf = requestAnimationFrame(step);
      } else {
        forceRender();
      }
    };
    if (prefersReducedMotion) {
      for (let i = 0; i < 300; i++) tickForces(positions, entities, edges, size);
      forceRender();
    } else {
      raf = requestAnimationFrame(step);
    }
    return () => {
      simulationRunning.current = false;
      cancelAnimationFrame(raf);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefersReducedMotion, entities, edges, size]);

  // Drag handlers
  const handleNodeDragStart = React.useCallback((entityId: string, clientX: number, clientY: number) => {
    const pos = positionsRef.current.get(entityId);
    if (!pos || !svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const svgX = (clientX - rect.left - view.x) / view.scale;
    const svgY = (clientY - rect.top - view.y) / view.scale;
    dragRef.current = { entityId, offsetX: pos.x - svgX, offsetY: pos.y - svgY };
    pos.pinned = true;
  }, [view]);

  const handleNodeDragMove = React.useCallback((clientX: number, clientY: number) => {
    const drag = dragRef.current;
    if (!drag || !svgRef.current) return;
    const pos = positionsRef.current.get(drag.entityId);
    if (!pos) return;
    const rect = svgRef.current.getBoundingClientRect();
    const svgX = (clientX - rect.left - view.x) / view.scale;
    const svgY = (clientY - rect.top - view.y) / view.scale;
    pos.x = svgX + drag.offsetX;
    pos.y = svgY + drag.offsetY;
    pos.vx = 0;
    pos.vy = 0;
    forceRender();
  }, [view, forceRender]);

  const handleNodeDragEnd = React.useCallback(() => {
    const drag = dragRef.current;
    if (drag) {
      const pos = positionsRef.current.get(drag.entityId);
      if (pos) pos.pinned = false;
    }
    dragRef.current = null;
  }, []);

  // Pan handlers
  const handleSvgPointerDown = React.useCallback((e: React.PointerEvent<SVGSVGElement>) => {
    if (dragRef.current) return;
    if ((e.target as SVGElement).closest("g[data-node]")) return;
    panRef.current = { startX: e.clientX, startY: e.clientY, viewX: view.x, viewY: view.y };
    (e.currentTarget as SVGSVGElement).setPointerCapture(e.pointerId);
  }, [view]);

  const handleSvgPointerMove = React.useCallback((e: React.PointerEvent<SVGSVGElement>) => {
    if (dragRef.current) {
      handleNodeDragMove(e.clientX, e.clientY);
      return;
    }
    const pan = panRef.current;
    if (!pan) return;
    setView((v) => ({ ...v, x: pan.viewX + (e.clientX - pan.startX), y: pan.viewY + (e.clientY - pan.startY) }));
  }, [handleNodeDragMove]);

  const handleSvgPointerUp = React.useCallback((e: React.PointerEvent<SVGSVGElement>) => {
    if (dragRef.current) { handleNodeDragEnd(); return; }
    panRef.current = null;
    (e.currentTarget as SVGSVGElement).releasePointerCapture(e.pointerId);
  }, [handleNodeDragEnd]);

  const handleWheel = React.useCallback((e: React.WheelEvent<SVGSVGElement>) => {
    e.preventDefault();
    const rect = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const delta = e.deltaY > 0 ? 0.92 : 1.08;
    setView((v) => {
      const newScale = Math.min(3, Math.max(0.25, v.scale * delta));
      const ratio = newScale / v.scale;
      return { scale: newScale, x: mx - (mx - v.x) * ratio, y: my - (my - v.y) * ratio };
    });
  }, []);

  const resetView = React.useCallback(() => {
    setView({ x: 0, y: 0, scale: 1 });
  }, []);

  const zoomIn = React.useCallback(() => {
    setView((v) => {
      const newScale = Math.min(3, v.scale * 1.25);
      const cx = size.width / 2;
      const cy = size.height / 2;
      const ratio = newScale / v.scale;
      return { scale: newScale, x: cx - (cx - v.x) * ratio, y: cy - (cy - v.y) * ratio };
    });
  }, [size]);

  const zoomOut = React.useCallback(() => {
    setView((v) => {
      const newScale = Math.max(0.25, v.scale * 0.8);
      const cx = size.width / 2;
      const cy = size.height / 2;
      const ratio = newScale / v.scale;
      return { scale: newScale, x: cx - (cx - v.x) * ratio, y: cy - (cy - v.y) * ratio };
    });
  }, [size]);

  // Filter edges by time
  const currentTimeIso = currentTime ? currentTime.toISOString() : null;
  const visibleEdges = edges.filter((e) => {
    if (currentTimeIso && e.occurred_at && e.occurred_at > currentTimeIso) return false;
    return true;
  });

  const focusId = hoveredNode ?? selectedNode;

  return (
    <section
      aria-label="Mapa de relaciones"
      className={cn(
        "relative flex h-full min-h-0 flex-col overflow-hidden rounded-[var(--radius-lg)] border border-[var(--color-border-default)] bg-[var(--color-canvas)]",
        className,
      )}
    >
      {/* Minimal top bar */}
      <header className="flex items-center justify-between border-b border-[var(--color-border-default)] bg-[var(--color-surface)]/60 px-3 py-2 backdrop-blur-sm">
        <span className="font-mono text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
          {entities.length} nodos · {visibleEdges.length} aristas
        </span>
        <div className="flex items-center gap-1">
          <button type="button" onClick={zoomOut} className="rounded p-1 text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text-primary)]" aria-label="Alejar">
            <ZoomOut className="h-3.5 w-3.5" />
          </button>
          <span className="min-w-[36px] text-center font-mono text-[9px] text-[var(--color-text-muted)]">
            {Math.round(view.scale * 100)}%
          </span>
          <button type="button" onClick={zoomIn} className="rounded p-1 text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text-primary)]" aria-label="Acercar">
            <ZoomIn className="h-3.5 w-3.5" />
          </button>
          <button type="button" onClick={resetView} className="rounded p-1 text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text-primary)]" aria-label="Restablecer vista">
            <Maximize2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </header>

      <div ref={containerRef} className="relative min-h-0 flex-1">
        <svg
          ref={svgRef}
          width={size.width}
          height={size.height}
          viewBox={`0 0 ${size.width} ${size.height}`}
          className={cn("block h-full w-full", dragRef.current ? "cursor-grabbing" : panRef.current ? "cursor-grabbing" : "cursor-grab")}
          role="img"
          aria-label="Grafo de entidades cruzadas"
          onPointerDown={handleSvgPointerDown}
          onPointerMove={handleSvgPointerMove}
          onPointerUp={handleSvgPointerUp}
          onWheel={handleWheel}
          style={{ touchAction: "none" }}
        >
          <defs>
            {/* Glow filter for highlighted edges */}
            <filter id="edge-glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur in="SourceGraphic" stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            {/* Node glow */}
            <filter id="node-glow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur in="SourceGraphic" stdDeviation="6" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            {/* Dot pattern background */}
            <pattern id="dot-grid" width="20" height="20" patternUnits="userSpaceOnUse">
              <circle cx="10" cy="10" r="0.6" fill="var(--color-border-default)" opacity="0.4" />
            </pattern>
          </defs>

          {/* Dot grid background */}
          <rect width={size.width} height={size.height} fill="url(#dot-grid)" />

          <g transform={`translate(${view.x},${view.y}) scale(${view.scale})`}>
            {/* Edges — curved bezier */}
            <g>
              {visibleEdges.map((edge) => {
                const a = positionsRef.current.get(edge.from);
                const b = positionsRef.current.get(edge.to);
                if (!a || !b) return null;
                const color = SEMANTIC_COLOR[edge.semantic];
                const width = 0.8 + edge.confidence * 2;
                const isHighlighted = focusId === edge.from || focusId === edge.to;
                const dimmed = focusId && !isHighlighted;

                const dx = b.x - a.x;
                const dy = b.y - a.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                const curvature = Math.min(40, dist * 0.15);
                const nx = -dy / (dist || 1);
                const ny = dx / (dist || 1);
                const mx = (a.x + b.x) / 2 + nx * curvature;
                const my = (a.y + b.y) / 2 + ny * curvature;
                const path = `M ${a.x} ${a.y} Q ${mx} ${my} ${b.x} ${b.y}`;

                return (
                  <g key={edge.id}>
                    {isHighlighted && (
                      <path
                        d={path}
                        fill="none"
                        stroke={color}
                        strokeWidth={width + 4}
                        strokeOpacity={0.12}
                        filter="url(#edge-glow)"
                      />
                    )}
                    <path
                      d={path}
                      fill="none"
                      stroke={color}
                      strokeWidth={isHighlighted ? width + 0.8 : width}
                      strokeOpacity={dimmed ? 0.08 : isHighlighted ? 0.8 : 0.35}
                      strokeLinecap="round"
                      style={{ transition: "stroke-opacity 200ms ease, stroke-width 200ms ease" }}
                    />
                    {isHighlighted && (
                      <text x={mx} y={my - 8} textAnchor="middle" className="pointer-events-none font-mono" fontSize={8} fill="var(--color-text-secondary)" opacity={0.8}>
                        {edge.type}
                      </text>
                    )}
                  </g>
                );
              })}
            </g>

            {/* Nodes */}
            <g>
              {entities.map((entity) => {
                const p = positionsRef.current.get(entity.id);
                if (!p) return null;
                const color = SEMANTIC_COLOR[entity.semantic];
                const r = entity.type === "person" ? 10 : entity.type === "company" ? 8 : 7;
                const isConnected = focusId
                  ? focusId === entity.id || edges.some(
                      (ed) => (ed.from === focusId && ed.to === entity.id) || (ed.to === focusId && ed.from === entity.id),
                    )
                  : true;
                const dimmed = !!focusId && !isConnected;
                const isSelected = selectedNode === entity.id;

                return (
                  <NodeGlyph
                    key={entity.id}
                    entity={entity}
                    x={p.x}
                    y={p.y}
                    r={r}
                    color={color}
                    dimmed={dimmed}
                    selected={isSelected}
                    onClick={(id) => {
                      setSelectedNode((prev) => (prev === id ? null : id));
                      onNodeClick?.(id);
                    }}
                    onHover={setHoveredNode}
                    onDragStart={handleNodeDragStart}
                  />
                );
              })}
            </g>
          </g>
        </svg>

        {/* Legend — bottom left */}
        <div className="pointer-events-none absolute bottom-2 left-2 flex flex-wrap gap-1">
          {(Object.keys(SEMANTIC_COLOR) as GraphSemantic[]).map((s) => (
            <span
              key={s}
              className="inline-flex items-center gap-1 rounded-full bg-[var(--color-canvas)]/80 px-2 py-0.5 font-mono text-[9px] backdrop-blur-sm"
              style={{ color: SEMANTIC_COLOR[s] }}
            >
              <span aria-hidden className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: SEMANTIC_COLOR[s] }} />
              {SEMANTIC_LABEL[s]}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Node
// ─────────────────────────────────────────────────────────────────────────────

function NodeGlyph({
  entity,
  x,
  y,
  r,
  color,
  dimmed,
  selected,
  onClick,
  onHover,
  onDragStart,
}: {
  entity: GraphEntity;
  x: number;
  y: number;
  r: number;
  color: string;
  dimmed: boolean;
  selected: boolean;
  onClick?: (id: string) => void;
  onHover?: (id: string | null) => void;
  onDragStart?: (id: string, clientX: number, clientY: number) => void;
}) {
  const isDragging = React.useRef(false);
  const startPos = React.useRef<{ x: number; y: number } | null>(null);

  return (
    <g
      data-node
      transform={`translate(${x},${y})`}
      tabIndex={0}
      role="button"
      aria-label={`${entity.name} — ${entity.type}`}
      className="cursor-grab outline-none active:cursor-grabbing"
      style={{ opacity: dimmed ? 0.12 : 1, transition: "opacity 200ms ease" }}
      onPointerDown={(ev) => {
        ev.stopPropagation();
        startPos.current = { x: ev.clientX, y: ev.clientY };
        isDragging.current = false;
        onDragStart?.(entity.id, ev.clientX, ev.clientY);
        (ev.currentTarget as SVGGElement).setPointerCapture(ev.pointerId);
      }}
      onPointerUp={(ev) => {
        (ev.currentTarget as SVGGElement).releasePointerCapture(ev.pointerId);
        if (!isDragging.current) onClick?.(entity.id);
        isDragging.current = false;
        startPos.current = null;
      }}
      onPointerMove={(ev) => {
        if (startPos.current) {
          const dx = ev.clientX - startPos.current.x;
          const dy = ev.clientY - startPos.current.y;
          if (Math.abs(dx) > 3 || Math.abs(dy) > 3) isDragging.current = true;
        }
      }}
      onPointerEnter={() => onHover?.(entity.id)}
      onPointerLeave={() => onHover?.(null)}
      onKeyDown={(ev) => {
        if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); onClick?.(entity.id); }
      }}
    >
      {/* Outer glow */}
      <circle r={r + 8} fill={color} opacity={selected ? 0.2 : 0.06} filter="url(#node-glow)" />
      {/* Selection ring */}
      {selected && (
        <circle r={r + 5} fill="none" stroke={color} strokeWidth={1} strokeDasharray="3 2" opacity={0.5} />
      )}
      {/* Core */}
      <circle r={r} fill={color} opacity={0.9} />
      <circle r={r} fill="none" stroke={color} strokeWidth={1.5} opacity={0.4} />
      {/* Inner highlight */}
      <circle r={r * 0.4} fill="white" opacity={0.15} cy={-r * 0.2} />
      {/* Label */}
      <text
        y={r + 13}
        textAnchor="middle"
        className="pointer-events-none font-mono"
        fontSize={9}
        fill="var(--color-text-primary)"
        opacity={0.85}
      >
        {truncate(entity.name, 22)}
      </text>
    </g>
  );
}

function truncate(s: string, n: number): string {
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}

// ─────────────────────────────────────────────────────────────────────────────
// Force simulation
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

  const REPULSION = 2200;
  for (let i = 0; i < ids.length; i++) {
    const a = positions.get(ids[i]);
    if (!a) continue;
    for (let j = i + 1; j < ids.length; j++) {
      const b = positions.get(ids[j]);
      if (!b) continue;
      const dx = a.x - b.x;
      const dy = a.y - b.y;
      const distSq = Math.max(100, dx * dx + dy * dy);
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

  for (const edge of edges) {
    const a = positions.get(edge.from);
    const b = positions.get(edge.to);
    if (!a || !b) continue;
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
    const rest = 120 + 50 / Math.max(0.2, edge.weight);
    const k = 0.025 * (0.5 + edge.confidence);
    const f = (dist - rest) * k;
    const ux = dx / dist;
    const uy = dy / dist;
    a.vx += ux * f;
    a.vy += uy * f;
    b.vx -= ux * f;
    b.vy -= uy * f;
  }

  const CENTER_FORCE = 0.01;
  for (const id of ids) {
    const p = positions.get(id);
    if (!p) continue;
    p.vx += (cx - p.x) * CENTER_FORCE;
    p.vy += (cy - p.y) * CENTER_FORCE;
  }

  const DAMPING = 0.8;
  const padding = 30;
  for (const id of ids) {
    const p = positions.get(id);
    if (!p) continue;
    if (p.pinned) { p.vx = 0; p.vy = 0; continue; }
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
