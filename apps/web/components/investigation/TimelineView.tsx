"use client";

/**
 * TimelineView — Investigation Floor "Cronología" mode.
 *
 * Atomic events derived from `state.claims` + `state.edges`, anchored to a
 * temporal field (claims: created_at; edges: occurred_at or
 * metadata.temporal_anchor / metadata.year). Events are bucketed by year and
 * laid out left-to-right within each row. Click on a marker emits
 * onEventClick(claim_id) so the shell can switch back to graph mode and zoom
 * to the corresponding node.
 *
 * @visx/timeline isn't installed in this worktree, so the rendering is a
 * lightweight SVG. The visual contract (year rows, color = investigator,
 * confidence = radius, click-to-zoom) is the same.
 */

import * as React from "react";
import type { Claim, InvestigatorCallsign } from "@sabueso/shared-types";
import { INVESTIGATORS } from "@sabueso/shared-types";

import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import type { GraphEdge } from "@/lib/mockInvestigationState";
import { cn } from "@/lib/utils";

export interface TimelineViewProps {
  claims: Claim[];
  edges: GraphEdge[];
  onEventClick?: (claimId: string) => void;
  className?: string;
}

interface TimelineEvent {
  id: string;
  /** Source entity (claim_id for claim events; edge_id for edge events). */
  refId: string;
  /** Anchor used to decide "where on the timeline does this sit". */
  date: Date;
  year: number;
  label: string;
  detail: string;
  kind: "claim" | "edge";
  agent?: InvestigatorCallsign;
  /** [0,1] — drives radius. */
  confidence: number;
}

const PROFILE_BY_CALLSIGN = new Map(INVESTIGATORS.map((i) => [i.callsign, i]));

export function TimelineView({ claims, edges, onEventClick, className }: TimelineViewProps) {
  const prefersReducedMotion = usePrefersReducedMotion();
  const events = React.useMemo(() => buildEvents(claims, edges), [claims, edges]);

  const grouped = React.useMemo(() => groupByYear(events), [events]);
  const years = React.useMemo(() => [...grouped.keys()].sort((a, b) => a - b), [grouped]);

  if (events.length === 0) {
    return (
      <section
        aria-label="Cronología"
        className={cn(
          "relative flex h-full min-h-0 flex-col overflow-hidden rounded-[var(--radius-lg)] border bg-[var(--color-canvas)]",
          className,
        )}
      >
        <header className="flex items-center justify-between border-b border-[var(--color-border-default)] bg-[var(--color-surface)] px-4 py-3">
          <h2 className="font-display text-lg">Cronología</h2>
          <span className="font-mono text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
            0 eventos
          </span>
        </header>
        <div className="flex flex-1 items-center justify-center px-6 text-center">
          <p className="text-sm text-[var(--color-text-muted)]">
            No hay eventos con anclaje temporal todavía.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section
      aria-label="Cronología"
      className={cn(
        "relative flex h-full min-h-0 flex-col overflow-hidden rounded-[var(--radius-lg)] border bg-[var(--color-canvas)]",
        className,
      )}
    >
      <header className="flex items-center justify-between border-b border-[var(--color-border-default)] bg-[var(--color-surface)] px-4 py-3">
        <h2 className="font-display text-lg">Cronología</h2>
        <span className="font-mono text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
          {events.length} eventos · {years.length} {years.length === 1 ? "año" : "años"}
        </span>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        <ol className="relative space-y-3" aria-label="Eventos por año">
          {years.map((year) => {
            const yearEvents = grouped.get(year) ?? [];
            return (
              <li key={year} className="relative">
                <div className="flex items-baseline gap-3">
                  <span className="w-12 shrink-0 font-display text-xl tabular-nums text-[var(--color-text-primary)]">
                    {year}
                  </span>
                  <div className="h-px flex-1 bg-[var(--color-border-default)]" />
                  <span className="font-mono text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
                    {yearEvents.length} {yearEvents.length === 1 ? "evento" : "eventos"}
                  </span>
                </div>

                <ul className="mt-2 flex flex-wrap gap-2 pl-14">
                  {yearEvents
                    .slice()
                    .sort((a, b) => a.date.getTime() - b.date.getTime())
                    .map((ev) => (
                      <TimelineDot
                        key={ev.id}
                        event={ev}
                        onClick={onEventClick}
                        prefersReducedMotion={prefersReducedMotion}
                      />
                    ))}
                </ul>
              </li>
            );
          })}
        </ol>
      </div>

      <footer className="border-t border-[var(--color-border-default)] bg-[var(--color-surface)] px-4 py-2 font-mono text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
        Click en evento → zoom al nodo en modo grafo
      </footer>
    </section>
  );
}

function TimelineDot({
  event,
  onClick,
  prefersReducedMotion,
}: {
  event: TimelineEvent;
  onClick?: (claimId: string) => void;
  prefersReducedMotion: boolean;
}) {
  const color =
    (event.agent && PROFILE_BY_CALLSIGN.get(event.agent)?.color) ||
    "var(--color-text-muted)";
  const interactive = event.kind === "claim";
  const handleActivate = () => {
    if (!interactive) return;
    onClick?.(event.refId);
  };

  return (
    <li>
      <button
        type="button"
        onClick={handleActivate}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            handleActivate();
          }
        }}
        disabled={!interactive}
        title={`${event.label} · ${event.detail}`}
        aria-label={`${event.label} en ${event.date.toLocaleDateString("es-PE")}`}
        className={cn(
          "group inline-flex max-w-[260px] items-center gap-2 rounded-[var(--radius-md)] border bg-[var(--color-surface)] px-2 py-1.5 text-left text-xs",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-canvas)]",
          interactive
            ? "cursor-pointer hover:border-[var(--color-border-strong)] hover:bg-[var(--color-surface-2)]"
            : "cursor-default opacity-80",
          !prefersReducedMotion && "transition-colors duration-150",
        )}
      >
        <span
          aria-hidden
          className="block shrink-0 rounded-full"
          style={{
            width: `${8 + event.confidence * 6}px`,
            height: `${8 + event.confidence * 6}px`,
            backgroundColor: color,
          }}
        />
        <span className="min-w-0 flex-1">
          <span className="block truncate font-medium text-[var(--color-text-primary)]">
            {event.label}
          </span>
          <span className="block truncate font-mono text-[10px] text-[var(--color-text-muted)]">
            {event.date.toLocaleDateString("es-PE", { month: "short", day: "2-digit" })} ·{" "}
            {event.detail}
          </span>
        </span>
      </button>
    </li>
  );
}

function buildEvents(claims: Claim[], edges: GraphEdge[]): TimelineEvent[] {
  const out: TimelineEvent[] = [];

  for (const c of claims) {
    const d = pickClaimDate(c);
    if (!d) continue;
    out.push({
      id: `claim-${c.id}`,
      refId: c.id,
      date: d,
      year: d.getFullYear(),
      label: c.predicate,
      detail: formatObjectValue(c.object_value),
      kind: "claim",
      agent: c.agent_callsign,
      confidence: clamp01(c.confidence),
    });
  }

  for (const e of edges) {
    const d = pickEdgeDate(e);
    if (!d) continue;
    out.push({
      id: `edge-${e.id}`,
      refId: e.id,
      date: d,
      year: d.getFullYear(),
      label: e.type.replace(/[-_]/g, " "),
      detail: `${e.from} → ${e.to}`,
      kind: "edge",
      confidence: clamp01(e.confidence),
    });
  }

  return out;
}

function pickClaimDate(c: Claim): Date | null {
  const ov = c.object_value as Record<string, unknown> | undefined;
  if (ov && typeof ov.temporal_anchor === "string") {
    const t = Date.parse(ov.temporal_anchor);
    if (!Number.isNaN(t)) return new Date(t);
  }
  if (ov && typeof ov.year === "number") {
    return new Date(ov.year, 0, 1);
  }
  const t = Date.parse(c.created_at);
  return Number.isNaN(t) ? null : new Date(t);
}

function pickEdgeDate(e: GraphEdge): Date | null {
  const meta = e.metadata as Record<string, unknown> | undefined;
  if (meta && typeof meta.temporal_anchor === "string") {
    const t = Date.parse(meta.temporal_anchor);
    if (!Number.isNaN(t)) return new Date(t);
  }
  if (meta && typeof meta.year === "number") {
    return new Date(meta.year as number, 0, 1);
  }
  if (e.occurred_at) {
    const t = Date.parse(e.occurred_at);
    if (!Number.isNaN(t)) return new Date(t);
  }
  return null;
}

function formatObjectValue(ov: Record<string, unknown>): string {
  if (!ov) return "—";
  if (typeof ov.amount_pen === "number") {
    return new Intl.NumberFormat("es-PE", {
      style: "currency",
      currency: "PEN",
      maximumFractionDigits: 0,
    }).format(ov.amount_pen);
  }
  const first = Object.values(ov)[0];
  if (typeof first === "string") return first;
  if (typeof first === "number") return String(first);
  return "—";
}

function groupByYear(events: TimelineEvent[]): Map<number, TimelineEvent[]> {
  const out = new Map<number, TimelineEvent[]>();
  for (const e of events) {
    const arr = out.get(e.year);
    if (arr) arr.push(e);
    else out.set(e.year, [e]);
  }
  return out;
}

function clamp01(n: number): number {
  if (Number.isNaN(n)) return 0;
  if (n < 0) return 0;
  if (n > 1) return 1;
  return n;
}
