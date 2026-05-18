"use client";

import * as React from "react";
import type { InvestigatorCallsign } from "@sabueso/shared-types";
import { INVESTIGATORS } from "@sabueso/shared-types";

import { cn } from "@/lib/utils";
import type { ActiveDelegation, AgentSnapshot } from "@/lib/mockInvestigationState";

import { InvestigatorAvatar } from "./InvestigatorAvatar";
import { STATUS_META, callsignColor, callsignDisplayName } from "./_meta";

export interface OperativesFloorProps {
  agents: Record<string, AgentSnapshot>;
  activeDelegations: ActiveDelegation[];
  onOpenDrilldown?: (callsign: InvestigatorCallsign) => void;
  order?: InvestigatorCallsign[];
  className?: string;
}

const DEFAULT_ORDER: InvestigatorCallsign[] = INVESTIGATORS.map((i) => i.callsign);

export function OperativesFloor({
  agents,
  activeDelegations,
  onOpenDrilldown,
  order = DEFAULT_ORDER,
  className,
}: OperativesFloorProps) {
  const orchestrator = order[0];
  const specialists = order.slice(1);

  const containerRef = React.useRef<HTMLDivElement | null>(null);
  const nodeRefs = React.useRef(new Map<string, HTMLButtonElement | null>());
  const [lines, setLines] = React.useState<Array<{ x1: number; y1: number; x2: number; y2: number; color: string; status: string }>>([]);
  const [containerSize, setContainerSize] = React.useState({ w: 0, h: 0 });

  const specialistsRef = React.useRef(specialists);
  specialistsRef.current = specialists;
  const delegationsRef = React.useRef(activeDelegations);
  delegationsRef.current = activeDelegations;

  const setNodeRef = React.useCallback(
    (callsign: string) => (el: HTMLButtonElement | null) => {
      nodeRefs.current.set(callsign, el);
    },
    [],
  );

  const measureLines = React.useCallback(() => {
    const container = containerRef.current;
    if (!container) return;
    const cRect = container.getBoundingClientRect();
    setContainerSize({ w: cRect.width, h: cRect.height });

    const orchestratorNode = nodeRefs.current.get(orchestrator);
    if (!orchestratorNode) return;
    const oRect = orchestratorNode.getBoundingClientRect();
    const ox = oRect.left - cRect.left + oRect.width / 2;
    const oy = oRect.top - cRect.top + oRect.height;

    const nextLines: Array<{ x1: number; y1: number; x2: number; y2: number; color: string; status: string }> = [];
    for (const s of specialistsRef.current) {
      const sNode = nodeRefs.current.get(s);
      if (!sNode) continue;
      const sRect = sNode.getBoundingClientRect();
      const sx = sRect.left - cRect.left + sRect.width / 2;
      const sy = sRect.top - cRect.top;

      const delegation = delegationsRef.current.find((d) => d.to === s);
      const color = callsignColor(s as InvestigatorCallsign);
      const status = delegation?.status ?? "idle";

      nextLines.push({ x1: ox, y1: oy, x2: sx, y2: sy, color, status });
    }
    setLines(nextLines);
  }, [orchestrator]);

  React.useEffect(() => {
    requestAnimationFrame(measureLines);
  }, [measureLines, specialists.length, activeDelegations]);

  React.useEffect(() => {
    const container = containerRef.current;
    if (!container || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => measureLines());
    observer.observe(container);
    return () => observer.disconnect();
  }, [measureLines]);

  return (
    <section
      ref={containerRef}
      aria-label="Operatives floor"
      className={cn("relative flex h-full min-h-0 flex-col items-center justify-start py-4", className)}
    >
      {/* SVG lines connecting orchestrator to specialists */}
      {containerSize.w > 0 && (
        <svg
          aria-hidden="true"
          className="pointer-events-none absolute inset-0"
          width={containerSize.w}
          height={containerSize.h}
          style={{ overflow: "visible" }}
        >
          {lines.map((line, i) => {
            const midY = line.y1 + (line.y2 - line.y1) * 0.45;
            const path = `M ${line.x1} ${line.y1} C ${line.x1} ${midY}, ${line.x2} ${midY}, ${line.x2} ${line.y2}`;
            const isActive = line.status === "running" || line.status === "done";
            return (
              <g key={i}>
                <path
                  d={path}
                  fill="none"
                  stroke={line.color}
                  strokeWidth={isActive ? 1.5 : 0.8}
                  strokeOpacity={isActive ? 0.5 : 0.2}
                  strokeDasharray={line.status === "running" ? "6 4" : undefined}
                />
                <circle cx={line.x2} cy={line.y2} r={2.5} fill={line.color} opacity={isActive ? 0.6 : 0.25} />
              </g>
            );
          })}
        </svg>
      )}

      {/* Orchestrator (root node) */}
      <div className="relative z-10 mb-6">
        <TreeNode
          ref={setNodeRef(orchestrator)}
          callsign={orchestrator}
          agent={agents[orchestrator] ?? { callsign: orchestrator, status: "idle" }}
          onClick={() => onOpenDrilldown?.(orchestrator)}
          isOrchestrator
        />
      </div>

      {/* Specialists (children) — responsive grid */}
      <div className="relative z-10 flex w-full flex-1 items-start justify-center">
        <div className="flex flex-wrap items-start justify-center gap-x-3 gap-y-5">
          {specialists.map((callsign) => {
            const snap: AgentSnapshot = agents[callsign] ?? { callsign, status: "idle" };
            return (
              <TreeNode
                ref={setNodeRef(callsign)}
                key={callsign}
                callsign={callsign}
                agent={snap}
                onClick={() => onOpenDrilldown?.(callsign)}
              />
            );
          })}
        </div>
      </div>

      <p className="sr-only" aria-live="polite">
        {activeDelegations
          .map((d) => `${d.from} delega ${d.task} a ${d.to} (${d.status})`)
          .join(". ")}
      </p>
    </section>
  );
}

interface TreeNodeProps {
  callsign: InvestigatorCallsign;
  agent: AgentSnapshot;
  isOrchestrator?: boolean;
  onClick?: () => void;
}

const TreeNode = React.forwardRef<HTMLButtonElement, TreeNodeProps>(
  ({ callsign, agent, isOrchestrator, onClick }, ref) => {
    const color = callsignColor(callsign);
    const name = callsignDisplayName(callsign);
    const statusMeta = STATUS_META[agent.status];
    const avatarSize = isOrchestrator ? 64 : 48;
    const visualState = agent.status === "blocked" ? "error" : agent.status === "idle" ? "normal" : "active";

    return (
      <button
        ref={ref}
        type="button"
        onClick={onClick}
        aria-label={`${name} — ${statusMeta.label}`}
        className={cn(
          "group relative flex flex-col items-center gap-1.5 rounded-lg px-2 py-2",
          "transition-all duration-150 hover:-translate-y-0.5 hover:bg-[var(--color-surface-2)]/50",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]",
          isOrchestrator && "px-4",
        )}
      >
        <div className="relative">
          <div
            aria-hidden="true"
            className="absolute inset-0 rounded-full blur-md"
            style={{
              background: `radial-gradient(closest-side, ${color}25, transparent 70%)`,
              width: avatarSize + 20,
              height: avatarSize + 20,
              top: "50%",
              left: "50%",
              transform: "translate(-50%, -50%)",
            }}
          />
          <div className="relative">
            <InvestigatorAvatar callsign={callsign} size={avatarSize} state={visualState} />
          </div>
        </div>

        <span
          className={cn(
            "max-w-[72px] truncate text-center font-mono text-[10px] leading-tight",
            isOrchestrator ? "font-semibold text-[var(--color-text-primary)]" : "text-[var(--color-text-secondary)]",
          )}
        >
          {name}
        </span>

        <span
          className="inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 font-mono text-[8px] uppercase tracking-wider"
          style={{ color: statusMeta.color, backgroundColor: `color-mix(in srgb, ${statusMeta.color} 12%, transparent)` }}
        >
          <span
            aria-hidden
            className={cn("h-1 w-1 rounded-full", statusMeta.dotPulse && "animate-pulse")}
            style={{ backgroundColor: statusMeta.color }}
          />
          {statusMeta.label}
        </span>

        {agent.detail && (
          <span className="max-w-[80px] truncate text-center font-mono text-[8px] leading-tight text-[var(--color-text-muted)]">
            {agent.detail}
          </span>
        )}
      </button>
    );
  },
);
TreeNode.displayName = "TreeNode";
