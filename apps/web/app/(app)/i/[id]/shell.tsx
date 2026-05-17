"use client";

import * as React from "react";
import Link from "next/link";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import {
  BarChart3,
  Clock,
  Download,
  FileText,
  MoreHorizontal,
  Network,
  Share2,
} from "lucide-react";
import type {
  AgentStatus,
  Claim,
  InvestigationEvent,
  InvestigatorCallsign,
  PlanStep,
  PlanGeneratedPayload,
  ClaimCreatedPayload,
  EdgeDiscoveredPayload,
} from "@sabueso/shared-types";

import { Button } from "@/components/ui/button";
import {
  DossierPanel,
  DrilldownPanel,
  InvestigationGraph,
  MissionControl,
  OperativesFloor,
  SankeyView,
  TimelineScrubber,
  TimelineView,
} from "@/components/investigation";
import { useInvestigation, type InvestigationState } from "@/hooks/useInvestigation";
import { useLocalStorageInvestigation } from "@/hooks/useLocalStorageInvestigation";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { cn } from "@/lib/utils";
import type {
  ActiveDelegation,
  AgentSnapshot,
  ComposedInvestigationState,
  GraphEdge,
  GraphEntity,
  GraphSemantic,
} from "@/lib/mockInvestigationState";

type FloorMode = "graph" | "sankey" | "timeline";
const FLOOR_MODE_KEY = "sabueso:floor-mode";
const FLOOR_MODES: Array<{ id: FloorMode; label: string; icon: React.ElementType }> = [
  { id: "graph", label: "Grafo", icon: Network },
  { id: "sankey", label: "Flujo $", icon: BarChart3 },
  { id: "timeline", label: "Cronología", icon: Clock },
];

function useFloorMode(): [FloorMode, (m: FloorMode) => void] {
  const [mode, setMode] = React.useState<FloorMode>("graph");
  // Hydrate from localStorage after mount (avoids SSR mismatch).
  React.useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = window.localStorage.getItem(FLOOR_MODE_KEY);
    if (stored === "graph" || stored === "sankey" || stored === "timeline") {
      setMode(stored);
    }
  }, []);
  const update = React.useCallback((next: FloorMode) => {
    setMode(next);
    if (typeof window !== "undefined") {
      try {
        window.localStorage.setItem(FLOOR_MODE_KEY, next);
      } catch {
        // ignore — privacy mode / quota
      }
    }
  }, []);
  return [mode, update];
}

type Labels = {
  missionControl: string;
  investigationFloor: string;
  dossier: string;
  loadingPlan: string;
  loadingFloor: string;
  loadingDossier: string;
  preparing: string;
};

export interface InvestigationShellProps {
  id: string;
  labels: Labels;
  /** When provided, the shell uses this state directly instead of opening the SSE stream. */
  state?: ComposedInvestigationState;
}

export function InvestigationShell({ id, labels, state: injectedState }: InvestigationShellProps) {
  const liveState = useLiveComposedState(id, !injectedState);
  const state = injectedState ?? liveState;

  const [drillTarget, setDrillTarget] = React.useState<InvestigatorCallsign | null>(null);
  const [scrubTime, setScrubTime] = React.useState<Date | null>(null);
  const [floorMode, setFloorMode] = useFloorMode();
  const prefersReducedMotion = usePrefersReducedMotion();

  const isLive = !injectedState && state.status === "running";
  const isStreamingDossier = state.status === "synthesizing";

  // When the user clicks an event in TimelineView, switch back to graph mode
  // and align the scrubber to the claim's timestamp so the graph filters down
  // to what was known at that point in time.
  const handleEventClick = React.useCallback(
    (claimId: string) => {
      const claim = state.claims.find((c) => c.id === claimId);
      if (claim) {
        const t = Date.parse(claim.created_at);
        if (!Number.isNaN(t)) setScrubTime(new Date(t));
      }
      setFloorMode("graph");
    },
    [state.claims, setFloorMode],
  );

  // Double-click on a scrubber dot: snap scrubber to that timestamp. The
  // graph already filters by `currentTime`, so the visible state matches.
  const handleEventZoom = React.useCallback((_ev: InvestigationEvent) => {
    // onTimeChange has already fired from TimelineScrubber (it sets the value
    // before emitting onEventZoom). Nothing else to do here for now.
  }, []);

  return (
    <main className="flex h-[calc(100dvh-64px)] min-h-0 w-full flex-col bg-[var(--color-canvas)]">
      <Header
        id={id}
        targetName={state.target_name || labels.preparing}
        progress={state.progress}
        isLive={isLive}
      />

      <div className="flex min-h-0 flex-1 flex-col gap-3 px-4 pb-3 lg:px-6">
        {/* Three-panel layout — desktop only. Mobile stacks vertically. */}
        <section className="flex min-h-0 flex-1">
          <div className="hidden h-full w-full lg:block">
            <PanelGroup direction="horizontal" className="h-full" autoSaveId={`shell-${id}`}>
              <Panel defaultSize={28} minSize={20} className="min-h-0">
                <MissionControl
                  plan={state.plan}
                  agents={state.agents}
                  events={state.events}
                  claims={state.claims}
                  className="h-full"
                />
              </Panel>
              <PanelResizeHandle className="w-1.5 cursor-col-resize bg-transparent transition-colors hover:bg-[var(--color-border-strong)]" />
              <Panel defaultSize={44} minSize={30} className="min-h-0">
                <FloorPanel
                  mode={floorMode}
                  onModeChange={setFloorMode}
                  entities={state.entities}
                  edges={state.edges}
                  claims={state.claims}
                  scrubTime={scrubTime}
                  onEventClick={handleEventClick}
                  prefersReducedMotion={prefersReducedMotion}
                  className="h-full"
                />
              </Panel>
              <PanelResizeHandle className="w-1.5 cursor-col-resize bg-transparent transition-colors hover:bg-[var(--color-border-strong)]" />
              <Panel defaultSize={28} minSize={20} className="min-h-0">
                <DossierPanel
                  dossier_md={state.dossier_md}
                  streaming={isStreamingDossier}
                  className="h-full"
                />
              </Panel>
            </PanelGroup>
          </div>

          {/* Mobile stack */}
          <div className="flex h-full w-full flex-col gap-3 overflow-y-auto lg:hidden">
            <div className="h-[420px] flex-none">
              <FloorPanel
                mode={floorMode}
                onModeChange={setFloorMode}
                entities={state.entities}
                edges={state.edges}
                claims={state.claims}
                scrubTime={scrubTime}
                onEventClick={handleEventClick}
                prefersReducedMotion={prefersReducedMotion}
                className="h-full"
              />
            </div>
            <MissionControl
              plan={state.plan}
              agents={state.agents}
              events={state.events}
              claims={state.claims}
              className="h-[480px] flex-none"
            />
            <DossierPanel
              dossier_md={state.dossier_md}
              streaming={isStreamingDossier}
              className="h-[600px] flex-none"
            />
          </div>
        </section>

        <OperativesFloor
          agents={state.agents}
          activeDelegations={state.activeDelegations}
          onOpenDrilldown={setDrillTarget}
        />

        <TimelineScrubber
          events={state.events}
          value={scrubTime}
          onTimeChange={setScrubTime}
          onEventZoom={handleEventZoom}
        />
      </div>

      <DrilldownPanel
        callsign={drillTarget}
        events={state.events}
        agents={state.agents}
        onOpenChange={(open) => {
          if (!open) setDrillTarget(null);
        }}
      />
    </main>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Investigation Floor — Grafo / Sankey / Timeline switcher
// ─────────────────────────────────────────────────────────────────────────────

interface FloorPanelProps {
  mode: FloorMode;
  onModeChange: (m: FloorMode) => void;
  entities: GraphEntity[];
  edges: GraphEdge[];
  claims: Claim[];
  scrubTime: Date | null;
  onEventClick: (claimId: string) => void;
  prefersReducedMotion: boolean;
  className?: string;
}

function FloorPanel({
  mode,
  onModeChange,
  entities,
  edges,
  claims,
  scrubTime,
  onEventClick,
  prefersReducedMotion,
  className,
}: FloorPanelProps) {
  // Render all three at once so React keeps state across switches; the inactive
  // ones are pointer-events:none with opacity 0. Cross-fade is CSS only — no
  // framer-motion dependency.
  const transitionMs = prefersReducedMotion ? 0 : 200;

  return (
    <div
      className={cn(
        "relative flex min-h-0 flex-col rounded-[var(--radius-lg)] bg-transparent",
        className,
      )}
    >
      <div
        role="tablist"
        aria-label="Modos de visualización"
        className="mb-2 inline-flex w-fit gap-1 rounded-[var(--radius-md)] border border-[var(--color-border-default)] bg-[var(--color-surface)] p-0.5"
      >
        {FLOOR_MODES.map((m) => {
          const active = m.id === mode;
          const Icon = m.icon;
          return (
            <button
              key={m.id}
              role="tab"
              type="button"
              aria-selected={active}
              aria-controls={`floor-panel-${m.id}`}
              onClick={() => onModeChange(m.id)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-[var(--radius-sm)] px-2.5 py-1 font-mono text-[10px] uppercase tracking-wider transition-colors",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] focus-visible:ring-offset-1 focus-visible:ring-offset-[var(--color-surface)]",
                active
                  ? "bg-[var(--color-accent)] text-white"
                  : "text-[var(--color-text-muted)] hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text-primary)]",
              )}
            >
              <Icon className="h-3 w-3" aria-hidden />
              {m.label}
            </button>
          );
        })}
      </div>

      <div className="relative min-h-0 flex-1">
        <FloorLayer id="graph" active={mode === "graph"} transitionMs={transitionMs}>
          <InvestigationGraph
            entities={entities}
            edges={edges}
            currentTime={scrubTime}
            className="h-full"
          />
        </FloorLayer>
        <FloorLayer id="sankey" active={mode === "sankey"} transitionMs={transitionMs}>
          <SankeyView entities={entities} edges={edges} className="h-full" />
        </FloorLayer>
        <FloorLayer id="timeline" active={mode === "timeline"} transitionMs={transitionMs}>
          <TimelineView claims={claims} edges={edges} onEventClick={onEventClick} className="h-full" />
        </FloorLayer>
      </div>
    </div>
  );
}

function FloorLayer({
  id,
  active,
  transitionMs,
  children,
}: {
  id: FloorMode;
  active: boolean;
  transitionMs: number;
  children: React.ReactNode;
}) {
  return (
    <div
      id={`floor-panel-${id}`}
      role="tabpanel"
      aria-hidden={!active}
      className={cn(
        "absolute inset-0 min-h-0",
        active ? "opacity-100" : "pointer-events-none opacity-0",
      )}
      style={{ transition: `opacity ${transitionMs}ms ease-out` }}
    >
      {children}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Header
// ─────────────────────────────────────────────────────────────────────────────

function Header({
  id,
  targetName,
  progress,
  isLive,
}: {
  id: string;
  targetName: string;
  progress: number;
  isLive: boolean;
}) {
  return (
    <header
      role="banner"
      className="sticky top-0 z-20 flex flex-col gap-2 border-b border-[var(--color-border-default)] bg-[var(--color-canvas)]/95 px-4 pb-2 pt-3 backdrop-blur lg:px-6"
    >
      <div className="flex items-baseline justify-between gap-4">
        <div className="min-w-0">
          <nav className="flex items-center gap-1 font-mono text-[11px] uppercase tracking-wider text-[var(--color-text-muted)]">
            <span>Sabueso</span>
            <span aria-hidden>›</span>
            <span>Investigaciones</span>
            <span aria-hidden>›</span>
            <span className="text-[var(--color-text-secondary)]">#INV-{id.slice(0, 8)}</span>
          </nav>
          <h1 className="mt-0.5 truncate font-display text-2xl tracking-tight text-[var(--color-text-primary)]">
            {targetName}
          </h1>
        </div>

        <div className="flex flex-none items-center gap-3 text-xs">
          <span
            aria-label={isLive ? "live" : "offline"}
            className={
              "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 font-mono text-[10px] uppercase " +
              (isLive
                ? "bg-[color-mix(in_srgb,var(--color-declared)_15%,transparent)] text-[var(--color-declared)]"
                : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)]")
            }
          >
            <span
              className={
                "h-1.5 w-1.5 rounded-full " +
                (isLive ? "animate-pulse-led bg-[var(--color-declared)]" : "bg-[var(--color-text-muted)]")
              }
            />
            {isLive ? "live" : "offline"}
          </span>
          <span className="font-mono tabular-nums text-[var(--color-text-secondary)]">
            {Math.round(progress)}%
          </span>
          <Button asChild variant="ghost" size="sm">
            <Link
              href={`/i/${id}/dossier`}
              aria-label="Vista dossier solamente"
              title="Vista dossier solamente"
            >
              <FileText className="h-3.5 w-3.5" />
              <span className="hidden sm:ml-1 sm:inline">Dossier</span>
            </Link>
          </Button>
          <Button variant="ghost" size="sm" aria-label="Compartir">
            <Share2 className="h-3.5 w-3.5" />
          </Button>
          <Button variant="ghost" size="sm" aria-label="Descargar PDF">
            <Download className="h-3.5 w-3.5" />
          </Button>
          <Button variant="ghost" size="icon" aria-label="Más opciones">
            <MoreHorizontal className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(progress)}
        className="h-1 overflow-hidden rounded-full bg-[var(--color-surface-2)]"
      >
        <div
          className="h-full bg-[var(--color-accent)] transition-[width] duration-500"
          style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
        />
      </div>
    </header>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Live state derivation
// ─────────────────────────────────────────────────────────────────────────────

const TYPE_SEMANTIC: GraphSemantic = "discovered";

function useLiveComposedState(id: string, enabled: boolean): ComposedInvestigationState {
  const { hydrated, save } = useLocalStorageInvestigation(enabled ? id : undefined);
  const { state } = useInvestigation(enabled ? id : undefined, { initialState: hydrated });

  React.useEffect(() => {
    if (!enabled) return;
    save?.(state);
  }, [enabled, state, save]);

  return React.useMemo(() => deriveComposedState(id, state), [id, state]);
}

function deriveComposedState(
  id: string,
  live: InvestigationState,
): ComposedInvestigationState {
  // Plan — pulled from the most recent plan_generated event.
  const planEvent = [...live.events]
    .reverse()
    .find((e) => e.type === "plan_generated");
  const plan: PlanStep[] =
    (planEvent?.payload as unknown as PlanGeneratedPayload | undefined)?.plan ?? [];

  // Agents — collapse the live agent timelines into snapshots.
  const agents: Record<string, AgentSnapshot> = {};
  for (const [callsign, t] of Object.entries(live.agents)) {
    agents[callsign] = {
      callsign: callsign as InvestigatorCallsign,
      status: t.status as AgentStatus,
    };
  }

  // Entities + edges — derived from claim_created and edge_discovered events.
  const entitiesById = new Map<string, GraphEntity>();
  const edges: GraphEdge[] = [];
  const claims: Claim[] = [];

  for (const e of live.events) {
    if (e.type === "claim_created") {
      const p = e.payload as unknown as ClaimCreatedPayload | undefined;
      if (!p) continue;
      if (!entitiesById.has(p.entity_id)) {
        entitiesById.set(p.entity_id, {
          id: p.entity_id,
          name: p.entity_id,
          type: "person",
          semantic: TYPE_SEMANTIC,
        });
      }
      claims.push({
        id: p.claim_id,
        investigation_id: id,
        entity_id: p.entity_id,
        predicate: p.predicate,
        object_value: p.object_value,
        source_url: p.source_url,
        source_extract: null,
        confidence: p.confidence,
        agent_callsign: p.agent,
        verified_by_jueza: false,
        created_at: e.created_at,
      });
    } else if (e.type === "edge_discovered") {
      const p = e.payload as unknown as EdgeDiscoveredPayload | undefined;
      if (!p) continue;
      if (!entitiesById.has(p.from_entity)) {
        entitiesById.set(p.from_entity, {
          id: p.from_entity,
          name: p.from_entity,
          type: "person",
          semantic: TYPE_SEMANTIC,
        });
      }
      if (!entitiesById.has(p.to_entity)) {
        entitiesById.set(p.to_entity, {
          id: p.to_entity,
          name: p.to_entity,
          type: "person",
          semantic: TYPE_SEMANTIC,
        });
      }
      edges.push({
        id: p.edge_id,
        from: p.from_entity,
        to: p.to_entity,
        type: p.edge_type,
        weight: p.weight,
        confidence: p.confidence,
        semantic: TYPE_SEMANTIC,
        occurred_at: e.created_at,
      });
    }
  }

  // Active delegations — synthesize from working agents (sabueso → working agent).
  const activeDelegations: ActiveDelegation[] = Object.values(agents)
    .filter((a) => a.callsign !== "sabueso" && (a.status === "working" || a.status === "blocked"))
    .map((a, i) => ({
      id: `live-del-${i}`,
      from: "sabueso",
      to: a.callsign,
      status: a.status === "blocked" ? "blocked" : "running",
      task: "delegación",
    }));

  return {
    id: live.id || id,
    target_name: "",
    status: live.status,
    progress: live.progress,
    plan,
    agents,
    entities: Array.from(entitiesById.values()),
    edges,
    claims,
    dossier_md: "",
    activeDelegations,
    events: live.events as InvestigationEvent[],
  };
}
