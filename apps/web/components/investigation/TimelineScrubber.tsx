"use client";

import * as React from "react";
import type { InvestigationEvent } from "@sabueso/shared-types";
import { INVESTIGATORS } from "@sabueso/shared-types";

import { cn } from "@/lib/utils";

export interface TimelineScrubberProps {
  events: InvestigationEvent[];
  /** Currently-selected time. If null, the thumb sits at the rightmost edge. */
  value?: Date | null;
  onTimeChange?: (date: Date) => void;
  /**
   * Fired when the user double-clicks one of the event dots — the consumer
   * should center / zoom the graph on that event (and snap the scrubber to
   * that timestamp).
   */
  onEventZoom?: (event: InvestigationEvent) => void;
  /** Optional override of the date range. Defaults to event min/max. */
  range?: { min: Date; max: Date };
  className?: string;
}

const PROFILE_BY_CALLSIGN = new Map(INVESTIGATORS.map((i) => [i.callsign, i]));

export function TimelineScrubber({
  events,
  value,
  onTimeChange,
  onEventZoom,
  range,
  className,
}: TimelineScrubberProps) {
  const trackRef = React.useRef<HTMLDivElement | null>(null);

  const [min, max] = React.useMemo(() => {
    if (range) return [range.min, range.max] as const;
    if (events.length === 0) {
      const now = new Date();
      const yearAgo = new Date(now.getTime() - 1000 * 60 * 60 * 24 * 365);
      return [yearAgo, now] as const;
    }
    const times = events.map((e) => Date.parse(e.created_at)).filter((t) => !Number.isNaN(t));
    return [new Date(Math.min(...times)), new Date(Math.max(...times))] as const;
  }, [events, range]);

  const currentValue = value ?? max;
  const pct = clamp01(
    (currentValue.getTime() - min.getTime()) / Math.max(1, max.getTime() - min.getTime()),
  );

  const onPointerDown = (ev: React.PointerEvent<HTMLDivElement>) => {
    const el = trackRef.current;
    if (!el) return;
    el.setPointerCapture(ev.pointerId);
    handle(ev.clientX);

    const onMove = (e: PointerEvent) => handle(e.clientX);
    const onUp = (e: PointerEvent) => {
      el.releasePointerCapture(e.pointerId);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  };

  const handle = (clientX: number) => {
    const el = trackRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const ratio = clamp01((clientX - r.left) / r.width);
    const t = min.getTime() + ratio * (max.getTime() - min.getTime());
    onTimeChange?.(new Date(t));
  };

  const onKeyDown = (ev: React.KeyboardEvent<HTMLDivElement>) => {
    const span = max.getTime() - min.getTime();
    const step = span / 50;
    if (ev.key === "ArrowLeft") {
      ev.preventDefault();
      onTimeChange?.(new Date(Math.max(min.getTime(), currentValue.getTime() - step)));
    } else if (ev.key === "ArrowRight") {
      ev.preventDefault();
      onTimeChange?.(new Date(Math.min(max.getTime(), currentValue.getTime() + step)));
    } else if (ev.key === "Home") {
      onTimeChange?.(min);
    } else if (ev.key === "End") {
      onTimeChange?.(max);
    }
  };

  // Year ticks across the visible span.
  const years = React.useMemo(() => {
    const out: Array<{ year: number; pct: number }> = [];
    const startY = min.getFullYear();
    const endY = max.getFullYear();
    for (let y = startY; y <= endY; y++) {
      const t = new Date(y, 0, 1).getTime();
      if (t < min.getTime() || t > max.getTime()) continue;
      out.push({
        year: y,
        pct: clamp01((t - min.getTime()) / (max.getTime() - min.getTime())),
      });
    }
    return out;
  }, [min, max]);

  return (
    <div
      className={cn(
        "relative h-12 w-full rounded-[var(--radius-md)] border bg-[var(--color-surface-2)]",
        className,
      )}
      role="group"
      aria-label="Línea de tiempo de la investigación"
    >
      {/* Year tick labels (above the track) */}
      <div className="pointer-events-none absolute inset-x-2 top-1 flex h-3 items-center">
        {years.map((y) => (
          <span
            key={y.year}
            className="absolute -translate-x-1/2 font-mono text-[9px] uppercase tracking-wider text-[var(--color-text-muted)]"
            style={{ left: `${y.pct * 100}%` }}
          >
            {y.year}
          </span>
        ))}
      </div>

      {/* Tick marks */}
      <div className="pointer-events-none absolute inset-x-2 top-5 flex h-1">
        {years.map((y) => (
          <span
            key={`tick-${y.year}`}
            className="absolute h-1 w-px bg-[var(--color-border-strong)]"
            style={{ left: `${y.pct * 100}%` }}
          />
        ))}
      </div>

      {/* Event dots */}
      <div
        ref={trackRef}
        onPointerDown={onPointerDown}
        role="slider"
        tabIndex={0}
        aria-valuemin={min.getTime()}
        aria-valuemax={max.getTime()}
        aria-valuenow={currentValue.getTime()}
        aria-valuetext={currentValue.toLocaleString("es-PE")}
        onKeyDown={onKeyDown}
        className={cn(
          "absolute inset-x-2 top-7 h-4 cursor-pointer rounded-full",
          "bg-[linear-gradient(to_bottom,transparent_45%,var(--color-border-default)_45%,var(--color-border-default)_55%,transparent_55%)]",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-surface-2)]",
        )}
      >
        {events.map((e) => {
          const t = Date.parse(e.created_at);
          if (Number.isNaN(t)) return null;
          const ePct = clamp01((t - min.getTime()) / Math.max(1, max.getTime() - min.getTime()));
          const color = e.agent_callsign
            ? (PROFILE_BY_CALLSIGN.get(e.agent_callsign)?.color ?? "var(--color-text-muted)")
            : "var(--color-text-muted)";
          return (
            <button
              key={e.id}
              type="button"
              aria-label={`Evento ${e.type} en ${new Date(t).toLocaleDateString("es-PE")}`}
              title={`${e.type}${e.agent_callsign ? ` · ${e.agent_callsign}` : ""}`}
              onPointerDown={(ev) => ev.stopPropagation()}
              onDoubleClick={(ev) => {
                ev.stopPropagation();
                onTimeChange?.(new Date(t));
                onEventZoom?.(e);
              }}
              className="absolute top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 cursor-pointer rounded-full p-0 outline-none transition-transform hover:scale-150 focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] focus-visible:ring-offset-1 focus-visible:ring-offset-[var(--color-surface-2)]"
              style={{ left: `${ePct * 100}%`, backgroundColor: color, border: "none" }}
            />
          );
        })}

        {/* Thumb */}
        <span
          aria-hidden
          className="absolute top-1/2 h-4 w-1 -translate-x-1/2 -translate-y-1/2 rounded-full bg-[var(--color-accent)] shadow"
          style={{ left: `${pct * 100}%` }}
        />
      </div>

      {/* Current value label (right-aligned) */}
      <p className="pointer-events-none absolute right-2 bottom-0.5 font-mono text-[9px] text-[var(--color-text-muted)]">
        {currentValue.toLocaleDateString("es-PE", {
          year: "numeric",
          month: "short",
          day: "2-digit",
        })}
      </p>
    </div>
  );
}

function clamp01(n: number): number {
  if (Number.isNaN(n)) return 0;
  if (n < 0) return 0;
  if (n > 1) return 1;
  return n;
}
