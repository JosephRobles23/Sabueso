/**
 * Replay engine — reproduce un set de InvestigationEvent pre-grabados con
 * timing artificial comprimido (target ~10s). Es el corazón del demo:
 * cero llamadas externas durante el pitch, indistinguible visualmente del
 * modo live.
 *
 * Diseño:
 *  - Pre-computa `scheduledMs[i]` = ms desde t=0 cuando event[i] debe firear,
 *    distribuyendo proporcionalmente el gap real entre eventos.
 *  - Avanza con un setTimeout encadenado (no rAF — pausar/resumir es trivial
 *    y 60fps no aporta nada para 10-30 eventos).
 *  - Soporta play/pause/next/end/seek. Seek hacia atrás resetea y re-emite
 *    los eventos 0..targetIndex sincrónicamente (el consumidor recibe un
 *    callback onReset antes para que limpie su state).
 *
 * El consumidor (useInvestigation) recibe los mismos `InvestigationEvent`
 * que el modo live; toda la lógica downstream (reducer, derivación de
 * grafo, dossier streaming) es idéntica.
 */
import type { InvestigationEvent } from "@sabueso/shared-types";

export type ReplayStatus = "idle" | "loading" | "playing" | "paused" | "ended";

export interface ReplayPlayerOptions {
  events: InvestigationEvent[];
  /** Duración objetivo del replay completo, en ms. Default 10000. */
  targetDurationMs?: number;
  /**
   * Tiempo mínimo entre dos eventos visibles, en ms. Evita que dos eventos
   * separados por <50ms en producción colapsen en un solo frame y se vean
   * como uno. Default 80ms.
   */
  minStepMs?: number;
  /** Llamado por cada evento, en orden. */
  onEvent: (event: InvestigationEvent) => void;
  /** Llamado al iniciar un seek hacia atrás — el consumidor debe limpiar state. */
  onReset?: () => void;
  /** Llamado en cada cambio de status/posición. */
  onChange?: (snapshot: ReplaySnapshot) => void;
}

export interface ReplaySnapshot {
  status: ReplayStatus;
  /** Índice del último evento ya emitido. -1 si todavía no se emitió ninguno. */
  currentIndex: number;
  /** Cantidad total de eventos cargados. */
  totalEvents: number;
  /** ms desde t=0 que ya transcurrieron del replay. */
  elapsedMs: number;
  /** ms totales del replay. */
  durationMs: number;
}

export interface ReplayPlayer {
  play(): void;
  pause(): void;
  /** Saltar al próximo evento (sin emitir los intermedios — ya emitidos por construcción). */
  next(): void;
  /** Saltar al último evento. */
  end(): void;
  /**
   * Seek a una posición de timeline (0..durationMs). Si va hacia atrás,
   * llama onReset y re-emite los eventos 0..targetIndex sincrónicamente.
   */
  seek(elapsedMs: number): void;
  /** Snapshot inmutable del estado actual. */
  snapshot(): ReplaySnapshot;
  /** Liberar timers. Idempotente. */
  dispose(): void;
}

/**
 * Computa los timestamps relativos comprimidos para cada evento.
 *
 * - Si hay <2 eventos: cada uno cae a t=0.
 * - Si todos los eventos tienen el mismo timestamp (test degenerado):
 *   distribuir en pasos iguales de targetDurationMs / (n-1).
 * - Si el gap real entre dos eventos es <50ms: forzar minStepMs en el
 *   replay para que no colapsen visualmente.
 */
export function computeSchedule(
  events: InvestigationEvent[],
  targetDurationMs: number,
  minStepMs: number,
): number[] {
  const n = events.length;
  if (n === 0) return [];
  if (n === 1) return [0];

  const t0 = Date.parse(events[0]!.created_at);
  const tLast = Date.parse(events[n - 1]!.created_at);
  const realSpanMs = Math.max(1, tLast - t0); // protege contra ÷0 con timestamps iguales

  const scheduled: number[] = new Array(n);
  scheduled[0] = 0;

  for (let i = 1; i < n; i++) {
    const ti = Date.parse(events[i]!.created_at);
    const rel = ti - t0;
    const proportional = Math.round((rel / realSpanMs) * targetDurationMs);
    // Forzar separación mínima del evento anterior:
    scheduled[i] = Math.max(scheduled[i - 1]! + minStepMs, proportional);
  }

  // Si por minStepMs nos pasamos del target total, comprimir uniformemente:
  const overshoot = scheduled[n - 1]! - targetDurationMs;
  if (overshoot > 0) {
    const factor = targetDurationMs / scheduled[n - 1]!;
    for (let i = 1; i < n; i++) scheduled[i] = Math.round(scheduled[i]! * factor);
  }

  return scheduled;
}

export function createReplayPlayer(options: ReplayPlayerOptions): ReplayPlayer {
  const events = options.events;
  const targetDurationMs = Math.max(1, options.targetDurationMs ?? 10_000);
  const minStepMs = Math.max(0, options.minStepMs ?? 80);
  const onEvent = options.onEvent;
  const onReset = options.onReset;
  const onChange = options.onChange;

  const scheduled = computeSchedule(events, targetDurationMs, minStepMs);
  const totalEvents = events.length;
  const durationMs = scheduled[scheduled.length - 1] ?? 0;

  let status: ReplayStatus = totalEvents === 0 ? "ended" : "paused";
  let currentIndex = -1; // último índice emitido
  let elapsedMs = 0;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let resumeAt = 0; // ms desde Date.now() base — punto de origen de la corrida actual
  let disposed = false;

  function emitChange(): void {
    if (!onChange) return;
    onChange({ status, currentIndex, totalEvents, elapsedMs, durationMs });
  }

  function clearTimer(): void {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
  }

  function scheduleNext(): void {
    if (disposed) return;
    if (status !== "playing") return;
    const nextIndex = currentIndex + 1;
    if (nextIndex >= totalEvents) {
      status = "ended";
      elapsedMs = durationMs;
      emitChange();
      return;
    }
    const targetMs = scheduled[nextIndex]!;
    const waitMs = Math.max(0, targetMs - elapsedMs);
    resumeAt = Date.now() - elapsedMs; // tracking del "tiempo cero" actual
    timer = setTimeout(() => {
      if (disposed) return;
      elapsedMs = targetMs;
      currentIndex = nextIndex;
      onEvent(events[nextIndex]!);
      emitChange();
      scheduleNext();
    }, waitMs);
  }

  /** Re-emite sincrónicamente eventos [0..targetIndex] tras un reset. */
  function flushToIndex(targetIndex: number): void {
    onReset?.();
    for (let i = 0; i <= targetIndex && i < totalEvents; i++) {
      onEvent(events[i]!);
    }
    currentIndex = Math.min(targetIndex, totalEvents - 1);
    elapsedMs = currentIndex >= 0 ? scheduled[currentIndex]! : 0;
  }

  // Inicializar status
  if (totalEvents === 0) emitChange();
  else emitChange();

  return {
    play() {
      if (disposed) return;
      if (status === "ended") return;
      if (status === "playing") return;
      status = "playing";
      emitChange();
      scheduleNext();
    },
    pause() {
      if (disposed) return;
      if (status !== "playing") return;
      // Capturar el tiempo transcurrido hasta este instante:
      elapsedMs = Math.min(durationMs, Date.now() - resumeAt);
      clearTimer();
      status = "paused";
      emitChange();
    },
    next() {
      if (disposed) return;
      clearTimer();
      const nextIndex = Math.min(currentIndex + 1, totalEvents - 1);
      if (nextIndex < 0) return;
      // Emitir 1 evento y reposicionar el reloj a su tiempo:
      currentIndex = nextIndex;
      elapsedMs = scheduled[nextIndex]!;
      onEvent(events[nextIndex]!);
      if (nextIndex === totalEvents - 1) {
        status = "ended";
        elapsedMs = durationMs;
      } else if (status === "playing") {
        emitChange();
        scheduleNext();
        return;
      }
      emitChange();
    },
    end() {
      if (disposed) return;
      clearTimer();
      // Emitir todos los eventos restantes en orden, sin delays:
      for (let i = currentIndex + 1; i < totalEvents; i++) onEvent(events[i]!);
      currentIndex = totalEvents - 1;
      elapsedMs = durationMs;
      status = "ended";
      emitChange();
    },
    seek(targetMs: number) {
      if (disposed) return;
      clearTimer();
      const clamped = Math.max(0, Math.min(durationMs, targetMs));
      // Encontrar el último evento cuyo scheduled <= clamped:
      let targetIndex = -1;
      for (let i = 0; i < totalEvents; i++) {
        if (scheduled[i]! <= clamped) targetIndex = i;
        else break;
      }
      if (targetIndex < currentIndex) {
        // Seek hacia atrás → reset + re-flush
        flushToIndex(targetIndex);
        elapsedMs = clamped;
      } else if (targetIndex > currentIndex) {
        // Seek hacia adelante → emitir lo que falta sin delay
        for (let i = currentIndex + 1; i <= targetIndex; i++) onEvent(events[i]!);
        currentIndex = targetIndex;
        elapsedMs = clamped;
      } else {
        // Mismo índice, sólo mover el reloj:
        elapsedMs = clamped;
      }
      if (currentIndex >= totalEvents - 1 && clamped >= durationMs) {
        status = "ended";
      } else if (status === "playing") {
        emitChange();
        scheduleNext();
        return;
      } else if (status === "ended" && clamped < durationMs) {
        status = "paused";
      }
      emitChange();
    },
    snapshot() {
      return { status, currentIndex, totalEvents, elapsedMs, durationMs };
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      clearTimer();
    },
  };
}
