"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type {
  AgentStatus,
  InvestigationEvent,
  InvestigatorCallsign,
} from "@sabueso/shared-types";
import type {
  ActiveDelegation,
  AgentSnapshot,
  ComposedInvestigationState,
  GraphEdge,
  GraphEntity,
} from "@/lib/mockInvestigationState";

type ReplayPhase = "idle" | "playing" | "streaming-dossier" | "complete";

export interface DemoReplayControls {
  phase: ReplayPhase;
  restart: () => void;
}

interface PayloadWithAgent {
  agent?: string;
}
interface PayloadWithTask {
  task?: string;
}
interface PayloadWithTool {
  tool?: string;
  args?: Record<string, unknown>;
}
interface PayloadWithClaimId {
  claim_id?: string;
  entity_id?: string;
  predicate?: string;
  confidence?: number;
  source_url?: string;
  object_value?: unknown;
}
interface PayloadWithEdge {
  edge_id?: string;
  from_entity?: string;
  to_entity?: string;
  edge_type?: string;
  weight?: number;
  confidence?: number;
}

const EVENT_DELAYS: Record<string, number> = {
  investigation_started: 600,
  plan_generated: 1200,
  agent_started: 800,
  tool_call: 1000,
  claim_created: 1200,
  edge_discovered: 600,
  agent_finished: 500,
  synthesis_started: 800,
  investigation_complete: 400,
};

const DOSSIER_CHUNK_SIZE = 12;
const DOSSIER_CHUNK_DELAY = 18;

function emptyState(final: ComposedInvestigationState): ComposedInvestigationState {
  const agents: Record<string, AgentSnapshot> = {};
  for (const key of Object.keys(final.agents)) {
    agents[key] = { callsign: key as InvestigatorCallsign, status: "idle" };
  }
  return {
    id: final.id,
    target_name: final.target_name,
    status: "pending",
    progress: 0,
    plan: [],
    agents: { sabueso: { callsign: "sabueso", status: "idle" } },
    entities: [],
    edges: [],
    claims: [],
    dossier_md: "",
    activeDelegations: [],
    events: [],
  };
}

function findEntity(final: ComposedInvestigationState, id: string): GraphEntity | undefined {
  return final.entities.find((e) => e.id === id);
}

function findEdge(final: ComposedInvestigationState, id: string): GraphEdge | undefined {
  return final.edges.find((e) => e.id === id);
}

function findClaim(final: ComposedInvestigationState, id: string) {
  return final.claims.find((c) => c.id === id);
}

function findDelegation(final: ComposedInvestigationState, to: string): ActiveDelegation | undefined {
  return final.activeDelegations.find((d) => d.to === to);
}

function applyEvent(
  prev: ComposedInvestigationState,
  event: InvestigationEvent,
  final: ComposedInvestigationState,
): ComposedInvestigationState {
  const next = { ...prev, events: [...prev.events, event] };
  const p = event.payload as Record<string, unknown>;

  switch (event.type) {
    case "investigation_started":
      return {
        ...next,
        status: "running",
        agents: {
          sabueso: { callsign: "sabueso", status: "thinking", detail: "Analizando objetivo…" },
        },
      };

    case "plan_generated":
      return {
        ...next,
        plan: final.plan,
        progress: 5,
        agents: {
          ...next.agents,
          sabueso: { callsign: "sabueso", status: "thinking", detail: "Coordinando plan" },
        },
      };

    case "agent_started": {
      const callsign = (p as PayloadWithAgent).agent ?? event.agent_callsign;
      if (!callsign) return next;
      const task = (p as PayloadWithTask).task ?? "";
      const del = findDelegation(final, callsign);
      return {
        ...next,
        agents: {
          ...next.agents,
          [callsign]: {
            callsign: callsign as InvestigatorCallsign,
            status: "working" as AgentStatus,
            detail: task,
          },
        },
        activeDelegations: del
          ? [...next.activeDelegations.filter((d) => d.to !== callsign), { ...del, status: "running" as const }]
          : next.activeDelegations,
        progress: Math.min(95, next.progress + 4),
      };
    }

    case "tool_call": {
      const callsign = (p as PayloadWithAgent).agent ?? event.agent_callsign;
      const tool = (p as PayloadWithTool).tool ?? "";
      if (!callsign) return next;
      const currentAgent = next.agents[callsign];
      return {
        ...next,
        agents: {
          ...next.agents,
          [callsign]: {
            ...currentAgent,
            callsign: callsign as InvestigatorCallsign,
            status: "working" as AgentStatus,
            detail: tool,
          },
        },
        progress: Math.min(95, next.progress + 2),
      };
    }

    case "claim_created": {
      const cp = p as unknown as PayloadWithClaimId;
      const claim = cp.claim_id ? findClaim(final, cp.claim_id) : undefined;
      const entityId = cp.entity_id;
      const newEntities = [...next.entities];
      if (entityId) {
        const ent = findEntity(final, entityId);
        if (ent && !newEntities.some((e) => e.id === entityId)) {
          newEntities.push(ent);
        }
      }
      return {
        ...next,
        claims: claim ? [...next.claims, claim] : next.claims,
        entities: newEntities,
        progress: Math.min(95, next.progress + 5),
      };
    }

    case "edge_discovered": {
      const ep = p as unknown as PayloadWithEdge;
      const edge = ep.edge_id ? findEdge(final, ep.edge_id) : undefined;
      const newEntities = [...next.entities];
      if (ep.from_entity) {
        const ent = findEntity(final, ep.from_entity);
        if (ent && !newEntities.some((e) => e.id === ep.from_entity)) newEntities.push(ent);
      }
      if (ep.to_entity) {
        const ent = findEntity(final, ep.to_entity);
        if (ent && !newEntities.some((e) => e.id === ep.to_entity)) newEntities.push(ent);
      }
      return {
        ...next,
        edges: edge ? [...next.edges, edge] : next.edges,
        entities: newEntities,
        progress: Math.min(95, next.progress + 3),
      };
    }

    case "agent_finished": {
      const callsign = (p as PayloadWithAgent).agent ?? event.agent_callsign;
      if (!callsign) return next;
      const finalAgent = final.agents[callsign];
      const del = findDelegation(final, callsign);
      return {
        ...next,
        agents: {
          ...next.agents,
          [callsign]: finalAgent ?? {
            callsign: callsign as InvestigatorCallsign,
            status: "done" as AgentStatus,
          },
        },
        activeDelegations: del
          ? [...next.activeDelegations.filter((d) => d.to !== callsign), { ...del, status: "done" as const }]
          : next.activeDelegations,
        progress: Math.min(95, next.progress + 4),
      };
    }

    case "synthesis_started":
      return {
        ...next,
        status: "synthesizing",
        progress: 90,
        agents: {
          ...next.agents,
          sabueso: { callsign: "sabueso", status: "working", detail: "Redactando dossier…" },
        },
      };

    case "investigation_complete":
      return {
        ...next,
        status: "complete",
        progress: 100,
        agents: final.agents,
        activeDelegations: final.activeDelegations,
      };

    default:
      return next;
  }
}

export function useDemoReplay(
  finalState: ComposedInvestigationState | undefined,
): [ComposedInvestigationState | undefined, DemoReplayControls] {
  const [state, setState] = useState<ComposedInvestigationState | undefined>(undefined);
  const [phase, setPhase] = useState<ReplayPhase>("idle");
  const cancelRef = useRef(false);
  const timeoutsRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  const cleanup = useCallback(() => {
    cancelRef.current = true;
    for (const t of timeoutsRef.current) clearTimeout(t);
    timeoutsRef.current = [];
  }, []);

  const play = useCallback(() => {
    if (!finalState) return;
    cleanup();
    cancelRef.current = false;

    const initial = emptyState(finalState);
    setState(initial);
    setPhase("playing");

    const events = finalState.events;
    let accumulated = initial;
    let delay = 400;

    for (let i = 0; i < events.length; i++) {
      const event = events[i];
      const eventDelay = EVENT_DELAYS[event.type] ?? 600;
      delay += eventDelay;

      const capturedIndex = i;
      const t = setTimeout(() => {
        if (cancelRef.current) return;
        accumulated = applyEvent(accumulated, event, finalState);
        setState({ ...accumulated });

        if (capturedIndex === events.length - 1) {
          streamDossier(accumulated, finalState);
        }
      }, delay);
      timeoutsRef.current.push(t);
    }

    function streamDossier(current: ComposedInvestigationState, final: ComposedInvestigationState) {
      if (cancelRef.current) return;
      setPhase("streaming-dossier");
      const fullMd = final.dossier_md;
      let charIndex = 0;

      function tick() {
        if (cancelRef.current) return;
        charIndex = Math.min(charIndex + DOSSIER_CHUNK_SIZE, fullMd.length);
        const partial = fullMd.slice(0, charIndex);
        setState((prev) => prev ? { ...prev, dossier_md: partial, status: "synthesizing" } : prev);

        if (charIndex < fullMd.length) {
          const t = setTimeout(tick, DOSSIER_CHUNK_DELAY);
          timeoutsRef.current.push(t);
        } else {
          const t = setTimeout(() => {
            if (cancelRef.current) return;
            setState((prev) => prev ? {
              ...prev,
              status: "complete",
              progress: 100,
              dossier_md: fullMd,
              agents: final.agents,
              activeDelegations: final.activeDelegations,
            } : prev);
            setPhase("complete");
          }, 300);
          timeoutsRef.current.push(t);
        }
      }

      const t = setTimeout(tick, 600);
      timeoutsRef.current.push(t);
    }
  }, [finalState, cleanup]);

  useEffect(() => {
    if (finalState) play();
    return cleanup;
  }, [finalState, play, cleanup]);

  const restart = useCallback(() => {
    play();
  }, [play]);

  return [state, { phase, restart }];
}
