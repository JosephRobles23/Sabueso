"use client";

import * as React from "react";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { Download, MoreHorizontal, Share2 } from "lucide-react";
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
  TimelineScrubber,
} from "@/components/investigation";
import { useInvestigation, type InvestigationState } from "@/hooks/useInvestigation";
import { useLocalStorageInvestigation } from "@/hooks/useLocalStorageInvestigation";
import type {
  ActiveDelegation,
  AgentSnapshot,
  ComposedInvestigationState,
  GraphEdge,
  GraphEntity,
  GraphSemantic,
} from "@/lib/mockInvestigationState";

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

  const isLive = !injectedState && state.status === "running";
  const isStreamingDossier = state.status === "synthesizing";

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
                <InvestigationGraph
                  entities={state.entities}
                  edges={state.edges}
                  onNodeClick={(_id) => {
                    /* graph node click → could open entity detail; out of S-12 scope */
                  }}
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
              <InvestigationGraph
                entities={state.entities}
                edges={state.edges}
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
