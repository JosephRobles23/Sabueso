"use client";

/**
 * LiveOrReplayToggle — selector replay/live para el home del demo.
 *
 * - "Replay (demos cacheadas)": expande una lista de los 5 demos ya
 *   cacheados; click → /i/<uuid>?mode=replay. Banner amarillo.
 * - "En vivo · 60-180s, costos reales": la búsqueda dispara
 *   POST /api/v1/investigations. Banner rojo.
 *
 * La selección se persiste en cookie `sabueso:demo-mode` para que el next
 * server render arranque en el mismo modo.
 */
import * as React from "react";
import Link from "next/link";
import { ChevronDown, FlaskConical, Radio } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { DEMO_MODE_COOKIE, type DemoMode } from "@/lib/demoMode";
import { DEMO_TARGETS, type DemoTarget } from "@/lib/demos";

export interface LiveOrReplayToggleProps {
  initialMode: DemoMode;
}

function writeCookie(mode: DemoMode): void {
  if (typeof document === "undefined") return;
  const oneMonth = 60 * 60 * 24 * 30;
  document.cookie = `${DEMO_MODE_COOKIE}=${mode}; path=/; max-age=${oneMonth}; SameSite=Lax`;
}

export function LiveOrReplayToggle({ initialMode }: LiveOrReplayToggleProps) {
  const [mode, setMode] = React.useState<DemoMode>(initialMode);
  const [open, setOpen] = React.useState(false);
  const wrapperRef = React.useRef<HTMLDivElement>(null);

  function change(next: DemoMode) {
    setMode(next);
    writeCookie(next);
    setOpen(false);
  }

  // Click fuera del dropdown lo cierra.
  React.useEffect(() => {
    if (!open) return;
    function onClick(e: MouseEvent) {
      if (!wrapperRef.current) return;
      if (!wrapperRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  return (
    <div className="space-y-3">
      <div ref={wrapperRef} className="relative inline-block">
        <button
          type="button"
          aria-haspopup="listbox"
          aria-expanded={open}
          onClick={() => setOpen((o) => !o)}
          className={cn(
            "inline-flex items-center gap-2 rounded-[var(--radius-md)] border bg-[var(--color-surface)] px-3 py-1.5 text-sm transition-colors",
            "hover:bg-[var(--color-surface-2)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]",
            mode === "live"
              ? "border-[var(--color-suspicious)] text-[var(--color-suspicious)]"
              : "border-[var(--color-ambiguous)] text-[var(--color-text-primary)]",
          )}
        >
          {mode === "replay" ? (
            <FlaskConical className="h-3.5 w-3.5" aria-hidden />
          ) : (
            <Radio className="h-3.5 w-3.5" aria-hidden />
          )}
          <span className="font-mono text-[11px] uppercase tracking-wider">
            {mode === "replay" ? "Replay" : "En vivo"}
          </span>
          <ChevronDown className="h-3.5 w-3.5" aria-hidden />
        </button>

        {open && (
          <ul
            role="listbox"
            className="absolute left-0 z-30 mt-1 w-72 overflow-hidden rounded-[var(--radius-md)] border border-[var(--color-border-strong)] bg-[var(--color-surface)] shadow-lg"
          >
            <li>
              <button
                type="button"
                role="option"
                aria-selected={mode === "replay"}
                onClick={() => change("replay")}
                className={cn(
                  "block w-full px-3 py-2 text-left text-sm transition-colors hover:bg-[var(--color-surface-2)]",
                  mode === "replay" && "bg-[var(--color-surface-2)]",
                )}
              >
                <span className="block font-medium">Replay (demos cacheadas)</span>
                <span className="block text-xs text-[var(--color-text-muted)]">
                  Cero llamadas externas. ~10s por investigación.
                </span>
              </button>
            </li>
            <li>
              <button
                type="button"
                role="option"
                aria-selected={mode === "live"}
                onClick={() => change("live")}
                className={cn(
                  "block w-full px-3 py-2 text-left text-sm transition-colors hover:bg-[var(--color-surface-2)]",
                  mode === "live" && "bg-[var(--color-surface-2)]",
                )}
              >
                <span className="block font-medium">En vivo · esto tomará 60-180s</span>
                <span className="block text-xs text-[var(--color-suspicious)]">
                  Investigación real con APIs activas, costos reales (~$0.65).
                </span>
              </button>
            </li>
          </ul>
        )}
      </div>

      {mode === "replay" ? <ReplayBanner /> : <LiveBanner />}

      {mode === "replay" && <ReplayDemoGrid demos={DEMO_TARGETS} />}
    </div>
  );
}

function ReplayBanner() {
  return (
    <div
      role="status"
      className="rounded-[var(--radius-md)] border border-[var(--color-ambiguous)]/40 bg-[color-mix(in_srgb,var(--color-ambiguous)_18%,transparent)] px-3 py-2 text-xs text-[var(--color-text-primary)]"
    >
      <strong className="font-mono uppercase tracking-wider text-[10px] text-[var(--color-ambiguous)]">
        Demo cacheado
      </strong>{" "}
      — los eventos se reproducen desde un snapshot grabado. Cero costos LLM,
      cero llamadas a APIs externas.
    </div>
  );
}

function LiveBanner() {
  return (
    <div
      role="alert"
      className="rounded-[var(--radius-md)] border border-[var(--color-suspicious)]/40 bg-[color-mix(in_srgb,var(--color-suspicious)_15%,transparent)] px-3 py-2 text-xs text-[var(--color-text-primary)]"
    >
      <strong className="font-mono uppercase tracking-wider text-[10px] text-[var(--color-suspicious)]">
        Investigación real
      </strong>{" "}
      — la búsqueda lanza una investigación contra APIs activas. Costos
      reales por LLM y posibles latencias gov-pe. Esperá 60-180s.
    </div>
  );
}

function ReplayDemoGrid({ demos }: { demos: DemoTarget[] }) {
  return (
    <ul className="grid gap-2 sm:grid-cols-2">
      {demos.map((d) => {
        const ready = d.investigation_id.length > 0;
        const href = ready ? `/i/${d.investigation_id}?mode=replay` : "#";
        return (
          <li key={d.slug}>
            {ready ? (
              <Link
                href={href}
                className="block rounded-[var(--radius-md)] border border-[var(--color-border-default)] bg-[var(--color-surface)] px-3 py-2 transition-colors hover:border-[var(--color-accent)] hover:bg-[var(--color-surface-2)]"
              >
                <DemoCardBody demo={d} ready />
              </Link>
            ) : (
              <div
                aria-disabled
                title="Pendiente — correr scripts/record-demos.ts y popular demos.ts"
                className="block cursor-not-allowed rounded-[var(--radius-md)] border border-dashed border-[var(--color-border-default)] bg-[var(--color-surface)]/50 px-3 py-2 opacity-60"
              >
                <DemoCardBody demo={d} ready={false} />
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function DemoCardBody({ demo, ready }: { demo: DemoTarget; ready: boolean }) {
  return (
    <>
      <div className="flex items-baseline justify-between gap-2">
        <span className="truncate text-sm font-medium">{demo.name}</span>
        <span className="font-mono text-[9px] uppercase tracking-wider text-[var(--color-text-muted)]">
          {ready ? demo.categoryLabel : "pendiente"}
        </span>
      </div>
      <p className="mt-0.5 truncate text-xs text-[var(--color-text-muted)]">
        {demo.caseLine}
      </p>
    </>
  );
}
