"use client";

import { useEffect, useMemo, useReducer, useRef, useState } from "react";

import { buildSseUrl } from "@/lib/api";
import { createSseClient, type SseMessage } from "@/lib/sse";
import {
  createReplayPlayer,
  type ReplayPlayer,
  type ReplaySnapshot,
} from "@/lib/replay";
import { fetchReplayEvents } from "@/lib/replayFetch";
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
  | { type: "reset"; id: string }
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
    case "reset":
      return initialState(action.id);
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

export type InvestigationMode = "live" | "replay";

export interface ReplayControls {
  snapshot: ReplaySnapshot;
  play(): void;
  pause(): void;
  next(): void;
  end(): void;
  seek(elapsedMs: number): void;
}

export interface UseInvestigationOptions {
  /** Hydrate from local storage before opening the stream. */
  initialState?: InvestigationState | null;
  /** Set to false to skip opening the stream (e.g. while waiting for an id). */
  enabled?: boolean;
  /**
   * "live" (default) abre SSE. "replay" fetcha eventos cacheados de
   * Supabase y los re-emite con timing comprimido a ~10s.
   */
  mode?: InvestigationMode;
  /** Override de duración total del replay, ms. Default 10000. */
  replayDurationMs?: number;
}

export interface UseInvestigationResult {
  state: InvestigationState;
  isLive: boolean;
  dispatch: React.Dispatch<Action>;
  /** Non-null sólo en mode=replay y cuando los eventos ya cargaron. */
  replay: ReplayControls | null;
}

export function useInvestigation(
  id: string | undefined,
  options: UseInvestigationOptions = {},
): UseInvestigationResult {
  const [state, dispatch] = useReducer(
    reducer,
    null,
    () => options.initialState ?? initialState(id ?? ""),
  );

  const mode: InvestigationMode = options.mode ?? "live";
  const enabled = options.enabled !== false && Boolean(id);
  const startingLastEventId = useRef(state.lastEventId);

  // ── Live (SSE) ────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!enabled || !id || mode !== "live") return;

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
  }, [enabled, id, mode]);

  // ── Replay ────────────────────────────────────────────────────────────────
  const playerRef = useRef<ReplayPlayer | null>(null);
  const [replaySnapshot, setReplaySnapshot] = useState<ReplaySnapshot | null>(null);
  const replayDurationMs = options.replayDurationMs;

  useEffect(() => {
    if (!enabled || !id || mode !== "replay") return;

    let disposed = false;
    setReplaySnapshot({
      status: "loading",
      currentIndex: -1,
      totalEvents: 0,
      elapsedMs: 0,
      durationMs: replayDurationMs ?? 10_000,
    });

    fetchReplayEvents(id).then((events) => {
      if (disposed) return;
      // Reset reducer: arrancamos con fresh state pero seteamos id.
      dispatch({ type: "reset", id });
      const player = createReplayPlayer({
        events,
        targetDurationMs: replayDurationMs,
        onEvent: (event) => dispatch({ type: "event", event }),
        onReset: () => dispatch({ type: "reset", id }),
        onChange: (snap) => {
          if (disposed) return;
          setReplaySnapshot(snap);
        },
      });
      playerRef.current = player;
      // En replay damos por buena la conexión (no hay SSE) → UI muestra "live"
      // (es el chip indistinguible visualmente del modo real, que el task pide).
      dispatch({ type: "connection", status: "open" });
      player.play();
    });

    return () => {
      disposed = true;
      playerRef.current?.dispose();
      playerRef.current = null;
    };
  }, [enabled, id, mode, replayDurationMs]);

  const replay: ReplayControls | null = useMemo(() => {
    if (mode !== "replay" || !replaySnapshot) return null;
    return {
      snapshot: replaySnapshot,
      play: () => playerRef.current?.play(),
      pause: () => playerRef.current?.pause(),
      next: () => playerRef.current?.next(),
      end: () => playerRef.current?.end(),
      seek: (ms: number) => playerRef.current?.seek(ms),
    };
  }, [mode, replaySnapshot]);

  const isLive = state.connection === "open";

  return useMemo(
    () => ({ state, isLive, dispatch, replay }),
    [state, isLive, replay],
  );
}

export { initialState as initialInvestigationState };
