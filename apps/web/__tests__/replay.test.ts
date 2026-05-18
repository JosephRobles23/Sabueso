import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { computeSchedule, createReplayPlayer } from "@/lib/replay";
import type { InvestigationEvent } from "@sabueso/shared-types";

function mkEvent(id: number, isoOffsetMs: number, type: string = "claim_created"): InvestigationEvent {
  return {
    id,
    investigation_id: "inv-test",
    type: type as InvestigationEvent["type"],
    agent_callsign: null,
    payload: {},
    created_at: new Date(1_700_000_000_000 + isoOffsetMs).toISOString(),
  };
}

describe("computeSchedule", () => {
  it("comprime un span real de 90s a 10s con timing proporcional", () => {
    // 4 eventos: t=0s, t=30s, t=60s, t=90s. Span real=90s.
    const events = [mkEvent(1, 0), mkEvent(2, 30_000), mkEvent(3, 60_000), mkEvent(4, 90_000)];
    const sched = computeSchedule(events, 10_000, 0);
    expect(sched).toEqual([0, Math.round(10_000 / 3), Math.round((20_000) / 3), 10_000]);
  });

  it("respeta minStepMs cuando dos eventos colapsan", () => {
    // 3 eventos casi simultáneos seguidos de uno lejano:
    const events = [mkEvent(1, 0), mkEvent(2, 10), mkEvent(3, 20), mkEvent(4, 90_000)];
    const sched = computeSchedule(events, 10_000, 80);
    // Los tres primeros se separan en pasos ≥80ms; el último igual cae en target.
    expect(sched[0]).toBe(0);
    expect(sched[1]).toBeGreaterThanOrEqual(80);
    expect(sched[2]).toBeGreaterThanOrEqual(sched[1]! + 80);
    expect(sched[3]).toBeLessThanOrEqual(10_000);
  });

  it("maneja 0/1 eventos sin pinchar", () => {
    expect(computeSchedule([], 10_000, 80)).toEqual([]);
    expect(computeSchedule([mkEvent(1, 0)], 10_000, 80)).toEqual([0]);
  });
});

describe("createReplayPlayer", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("emite todos los eventos en orden cuando avanza tiempo", () => {
    const events = [mkEvent(1, 0), mkEvent(2, 30_000), mkEvent(3, 60_000), mkEvent(4, 90_000)];
    const received: number[] = [];
    const player = createReplayPlayer({
      events,
      targetDurationMs: 10_000,
      minStepMs: 0,
      onEvent: (e) => received.push(e.id),
    });
    player.play();
    vi.advanceTimersByTime(10_500);
    expect(received).toEqual([1, 2, 3, 4]);
    expect(player.snapshot().status).toBe("ended");
    player.dispose();
  });

  it("pausa y reanuda sin perder eventos", () => {
    const events = [mkEvent(1, 0), mkEvent(2, 60_000), mkEvent(3, 90_000)];
    const received: number[] = [];
    const player = createReplayPlayer({
      events,
      targetDurationMs: 9_000,
      minStepMs: 0,
      onEvent: (e) => received.push(e.id),
    });
    player.play();
    vi.advanceTimersByTime(1_000);
    expect(received).toContain(1);
    player.pause();
    const pausedSnap = player.snapshot();
    expect(pausedSnap.status).toBe("paused");
    vi.advanceTimersByTime(5_000); // mientras está pausado nada debería pasar
    expect(received.length).toBe(1);
    player.play();
    vi.advanceTimersByTime(10_000);
    expect(received).toEqual([1, 2, 3]);
    player.dispose();
  });

  it("end() salta al final emitiendo el resto sin delay", () => {
    const events = [mkEvent(1, 0), mkEvent(2, 30_000), mkEvent(3, 90_000)];
    const received: number[] = [];
    const player = createReplayPlayer({
      events,
      targetDurationMs: 10_000,
      minStepMs: 0,
      onEvent: (e) => received.push(e.id),
    });
    player.end();
    expect(received).toEqual([1, 2, 3]);
    expect(player.snapshot().status).toBe("ended");
    player.dispose();
  });

  it("seek hacia atrás resetea y re-emite", () => {
    const events = [mkEvent(1, 0), mkEvent(2, 30_000), mkEvent(3, 90_000)];
    const received: number[] = [];
    let resets = 0;
    const player = createReplayPlayer({
      events,
      targetDurationMs: 9_000,
      minStepMs: 0,
      onEvent: (e) => received.push(e.id),
      onReset: () => {
        resets += 1;
      },
    });
    player.end();
    expect(received).toEqual([1, 2, 3]);
    // Seek hacia atrás a t=0 → reset + re-flush sólo del primer evento (cuyo scheduled=0)
    received.length = 0;
    player.seek(0);
    expect(resets).toBe(1);
    expect(received).toEqual([1]);
    player.dispose();
  });
});
