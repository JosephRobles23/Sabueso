"use client";

import { useEffect, useMemo, useReducer, useRef } from "react";

import { buildSseUrl } from "@/lib/api";
import { createSseClient, type SseMessage } from "@/lib/sse";
import type {
  EventType,
  InvestigationEvent,
  InvestigationStatus,
  InvestigatorCallsign,
} from "@sabueso/shared-types";

export interface AgentTimeline {
  callsign: InvestigatorCallsign;
  status: "idle" | "thinking" | "working" | "blocked" | "done";
  lastUpdate: number;
}

export interface InvestigationState {
  id: string;
  status: InvestigationStatus;
  progress: number;
  agents: Record<string, AgentTimeline>;
  events: InvestigationEvent[];
  lastEventId: string | null;
  connection: "idle" | "open" | "reconnecting" | "closed";
  error: string | null;
}

type Action =
  | { type: "connection"; status: InvestigationState["connection"] }
  | { type: "event"; event: InvestigationEvent }
  | { type: "hydrate"; state: InvestigationState }
  | { type: "error"; error: string };

const TERMINAL: ReadonlySet<EventType> = new Set([
  "investigation_complete",
  "investigation_failed",
]);

function reducer(state: InvestigationState, action: Action): InvestigationState {
  switch (action.type) {
    case "connection":
      return { ...state, connection: action.status };
    case "hydrate":
      return action.state;
    case "error":
      return { ...state, error: action.error };
    case "event": {
      const event = action.event;
      const next: InvestigationState = {
        ...state,
        lastEventId: String(event.id),
        events: [...state.events, event].slice(-500),
      };

      if (event.agent_callsign) {
        const prev = state.agents[event.agent_callsign];
        const status = mapAgentStatus(event.type, prev?.status);
        next.agents = {
          ...state.agents,
          [event.agent_callsign]: {
            callsign: event.agent_callsign,
            status,
            lastUpdate: Date.parse(event.created_at) || Date.now(),
          },
        };
      }

      const progress = (event.payload as { progress_pct?: number } | null)?.progress_pct;
      if (typeof progress === "number") next.progress = progress;

      if (event.type === "investigation_started") next.status = "running";
      else if (event.type === "synthesis_started") next.status = "synthesizing";
      else if (event.type === "verification_done") next.status = "verifying";
      else if (TERMINAL.has(event.type)) {
        next.status = event.type === "investigation_complete" ? "complete" : "failed";
      }

      return next;
    }
    default:
      return state;
  }
}

function mapAgentStatus(
  type: EventType,
  previous?: AgentTimeline["status"],
): AgentTimeline["status"] {
  switch (type) {
    case "agent_started":
      return "working";
    case "tool_call":
    case "claim_created":
    case "edge_discovered":
      return "working";
    case "agent_finished":
      return "done";
    case "investigation_failed":
      return "blocked";
    default:
      return previous ?? "idle";
  }
}

function initialState(id: string): InvestigationState {
  return {
    id,
    status: "pending",
    progress: 0,
    agents: {},
    events: [],
    lastEventId: null,
    connection: "idle",
    error: null,
  };
}

export interface UseInvestigationOptions {
  /** Hydrate from local storage before opening the stream. */
  initialState?: InvestigationState | null;
  /** Set to false to skip opening the stream (e.g. while waiting for an id). */
  enabled?: boolean;
}

export function useInvestigation(id: string | undefined, options: UseInvestigationOptions = {}) {
  const [state, dispatch] = useReducer(
    reducer,
    null,
    () => options.initialState ?? initialState(id ?? ""),
  );

  const enabled = options.enabled !== false && Boolean(id);
  const startingLastEventId = useRef(state.lastEventId);

  useEffect(() => {
    if (!enabled || !id) return;

    const client = createSseClient({
      buildUrl: (lastEventId) => buildSseUrl(id, lastEventId ?? startingLastEventId.current),
      onStatusChange: (status) => dispatch({ type: "connection", status }),
      onMessage: (message: SseMessage) => {
        if (message.type === "open" || message.type === "reconnecting") return;
        const payload = message.data as Partial<InvestigationEvent> | null;
        if (!payload || typeof payload !== "object") return;
        const event: InvestigationEvent = {
          id: Number(message.id ?? payload.id ?? Date.now()),
          investigation_id: id,
          type: (payload.type ?? "heartbeat") as EventType,
          agent_callsign: payload.agent_callsign ?? null,
          payload: payload.payload ?? {},
          created_at: payload.created_at ?? new Date().toISOString(),
        };
        dispatch({ type: "event", event });
      },
    });

    return () => client.close();
  }, [enabled, id]);

  const isLive = state.connection === "open";

  return useMemo(() => ({ state, isLive, dispatch }), [state, isLive]);
}

export { initialState as initialInvestigationState };
