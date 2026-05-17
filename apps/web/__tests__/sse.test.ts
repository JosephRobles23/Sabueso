import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { buildSseUrl } from "@/lib/api";
import { createSseClient } from "@/lib/sse";

class FakeEventSource {
  static instances: FakeEventSource[] = [];

  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  readyState = 0;

  constructor(public url: string) {
    FakeEventSource.instances.push(this);
  }

  open() {
    this.readyState = 1;
    this.onopen?.(new Event("open"));
  }

  emit(data: unknown, id?: string) {
    this.onmessage?.(
      new MessageEvent("message", {
        data: JSON.stringify(data),
        lastEventId: id ?? "",
      }),
    );
  }

  fail() {
    this.readyState = 2;
    this.onerror?.(new Event("error"));
  }

  close() {
    this.readyState = 2;
  }
}

describe("createSseClient", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    FakeEventSource.instances = [];
    // @ts-expect-error inject fake into jsdom global
    globalThis.EventSource = FakeEventSource;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("re-opens the connection with last_event_id as a query param", () => {
    const messages: unknown[] = [];
    const client = createSseClient({
      buildUrl: (lastEventId) => buildSseUrl("abc", lastEventId),
      onMessage: (message) => messages.push(message),
      initialBackoffMs: 100,
    });

    const first = FakeEventSource.instances[0]!;
    first.open();
    first.emit({ type: "agent_started", agent_callsign: "el-contador" }, "42");

    expect(first.url).toContain("/api/v1/investigations/abc/events");
    expect(first.url).not.toContain("last_event_id");

    first.fail();
    vi.advanceTimersByTime(100);

    const second = FakeEventSource.instances[1]!;
    expect(second).toBeDefined();
    expect(second.url).toContain("last_event_id=42");

    client.close();
  });

  it("applies exponential backoff between retries", () => {
    const client = createSseClient({
      buildUrl: () => "http://localhost/events",
      onMessage: () => {},
      initialBackoffMs: 100,
      maxBackoffMs: 1000,
    });

    FakeEventSource.instances[0]!.fail();
    vi.advanceTimersByTime(100);
    expect(FakeEventSource.instances.length).toBe(2);

    FakeEventSource.instances[1]!.fail();
    vi.advanceTimersByTime(199);
    expect(FakeEventSource.instances.length).toBe(2);
    vi.advanceTimersByTime(1);
    expect(FakeEventSource.instances.length).toBe(3);

    client.close();
  });
});
