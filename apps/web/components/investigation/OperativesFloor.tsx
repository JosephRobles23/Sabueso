"use client";

import * as React from "react";
import type { InvestigatorCallsign } from "@sabueso/shared-types";
import { INVESTIGATORS } from "@sabueso/shared-types";

import { cn } from "@/lib/utils";

import { DelegationArrow, type DelegationStatus, type Point } from "./DelegationArrow";
import { InvestigatorWorkstation } from "./InvestigatorWorkstation";
import type { ActiveDelegation, AgentSnapshot } from "@/lib/mockInvestigationState";

export interface OperativesFloorProps {
  agents: Record<string, AgentSnapshot>;
  activeDelegations: ActiveDelegation[];
  onOpenDrilldown?: (callsign: InvestigatorCallsign) => void;
  /** Visual ordering. Default: orchestrator first, then specialists in declaration order. */
  order?: InvestigatorCallsign[];
  className?: string;
}

interface AnchorRect {
  x: number;
  y: number;
}

const DEFAULT_ORDER: InvestigatorCallsign[] = INVESTIGATORS.map((i) => i.callsign);

export function OperativesFloor({
  agents,
  activeDelegations,
  onOpenDrilldown,
  order = DEFAULT_ORDER,
  className,
}: OperativesFloorProps) {
  const containerRef = React.useRef<HTMLDivElement | null>(null);
  const refs = React.useRef(new Map<InvestigatorCallsign, HTMLButtonElement | null>());
  const [anchors, setAnchors] = React.useState<Record<string, AnchorRect>>({});
  const [overlay, setOverlay] = React.useState<{ width: number; height: number }>({
    width: 0,
    height: 0,
  });

  const setRef = React.useCallback(
    (callsign: InvestigatorCallsign) => (node: HTMLButtonElement | null) => {
      refs.current.set(callsign, node);
    },
    [],
  );

  // Measure cubicle positions relative to the container, post-layout. We measure
  // the *top-center* of each workstation — the delegation arrow bows over the
  // floor with a quadratic Bezier (arc = 40 by default).
  const measure = React.useCallback(() => {
    const container = containerRef.current;
    if (!container) return;
    const cRect = container.getBoundingClientRect();
    const next: Record<string, AnchorRect> = {};
    for (const [callsign, node] of refs.current.entries()) {
      if (!node) continue;
      const r = node.getBoundingClientRect();
      next[callsign] = {
        x: r.left - cRect.left + r.width / 2,
        y: r.top - cRect.top + 10, // slightly inside the top of the placard
      };
    }
    setAnchors(next);
    setOverlay({ width: container.scrollWidth, height: container.clientHeight });
  }, []);

  React.useLayoutEffect(() => {
    measure();
  }, [measure, order]);

  React.useEffect(() => {
    const container = containerRef.current;
    if (!container || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => measure());
    observer.observe(container);
    return () => observer.disconnect();
  }, [measure]);

  return (
    <section
      aria-label="Operatives floor"
      className={cn(
        "relative rounded-[var(--radius-lg)] border bg-[var(--color-surface-2)] p-4",
        className,
      )}
    >
      <header className="mb-3 flex items-baseline justify-between">
        <h2 className="font-display text-lg text-[var(--color-text-primary)]">
          Operatives Floor
        </h2>
        <span className="font-mono text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
          {Object.values(agents).filter((a) => a.status === "working" || a.status === "thinking").length} activos
        </span>
      </header>

      <div
        ref={containerRef}
        className="relative overflow-x-auto pb-2"
        role="group"
        aria-label="Investigadores"
      >
        <div className="relative grid min-w-[640px] grid-cols-8 gap-2 md:gap-3">
          {order.map((callsign) => {
            const snap: AgentSnapshot = agents[callsign] ?? {
              callsign,
              status: "idle",
            };
            return (
              <InvestigatorWorkstation
                key={callsign}
                ref={setRef(callsign)}
                callsign={callsign}
                status={snap.status}
                detail={snap.detail}
                onClick={() => onOpenDrilldown?.(callsign)}
              />
            );
          })}
        </div>

        {/* Delegation overlay — absolutely positioned, sized to the scrollable row. */}
        {overlay.width > 0 && Object.keys(anchors).length > 0 ? (
          <svg
            aria-hidden="true"
            className="pointer-events-none absolute inset-0"
            width={overlay.width}
            height={overlay.height}
            viewBox={`0 0 ${overlay.width} ${overlay.height}`}
          >
            {activeDelegations.map((d) => {
              const from = anchors[d.from];
              const to = anchors[d.to];
              if (!from || !to) return null;
              return (
                <DelegationArrow
                  key={d.id}
                  from={normalize(from)}
                  to={normalize(to)}
                  status={d.status as DelegationStatus}
                  fromCallsign={d.from}
                  arc={36}
                />
              );
            })}
          </svg>
        ) : null}
      </div>

      {/* Screen-reader summary of active delegations. */}
      <p className="sr-only" aria-live="polite">
        {activeDelegations
          .map((d) => `${d.from} delega ${d.task} a ${d.to} (${d.status})`)
          .join(". ")}
      </p>
    </section>
  );
}

function normalize(p: AnchorRect): Point {
  return { x: p.x, y: p.y };
}
