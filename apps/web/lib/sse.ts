import type { EventType } from "@sabueso/shared-types";

export interface SseMessage<P = unknown> {
  id: string | null;
  type: EventType | "open" | "error" | "reconnecting";
  data: P;
}

export interface SseClientOptions {
  /** Build the URL for the next connection. Receives the last event id, if any. */
  buildUrl: (lastEventId: string | null) => string;
  /** Backoff (ms) between reconnect attempts; capped automatically. */
  initialBackoffMs?: number;
  maxBackoffMs?: number;
  onMessage: (message: SseMessage) => void;
  onStatusChange?: (status: "open" | "closed" | "reconnecting") => void;
}

/**
 * Native EventSource with our own reconnect loop. We close + recreate the connection
 * on every error so the server sees a fresh `last_event_id` query param (EventSource
 * cannot send custom headers, so we cannot rely on the Last-Event-ID header).
 */
export function createSseClient(options: SseClientOptions) {
  const initial = options.initialBackoffMs ?? 500;
  const max = options.maxBackoffMs ?? 10_000;

  let source: EventSource | null = null;
  let lastEventId: string | null = null;
  let stopped = false;
  let backoff = initial;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  function connect() {
    if (stopped) return;
    const url = options.buildUrl(lastEventId);
    const es = new EventSource(url);
    source = es;

    es.onopen = () => {
      backoff = initial;
      options.onStatusChange?.("open");
      options.onMessage({ id: lastEventId, type: "open", data: null });
    };

    es.onmessage = (event) => {
      if (event.lastEventId) lastEventId = event.lastEventId;
      let parsed: unknown = event.data;
      try {
        parsed = JSON.parse(event.data);
      } catch {
        /* keep raw string */
      }
      const message = parsed as { type?: EventType };
      options.onMessage({
        id: event.lastEventId || null,
        type: message?.type ?? "heartbeat",
        data: parsed,
      });
    };

    es.onerror = () => {
      es.close();
      source = null;
      if (stopped) return;
      options.onStatusChange?.("reconnecting");
      options.onMessage({ id: lastEventId, type: "reconnecting", data: { backoffMs: backoff } });
      reconnectTimer = setTimeout(connect, backoff);
      backoff = Math.min(max, backoff * 2);
    };
  }

  connect();

  return {
    close() {
      stopped = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      source?.close();
      source = null;
      options.onStatusChange?.("closed");
    },
    get lastEventId() {
      return lastEventId;
    },
  };
}
