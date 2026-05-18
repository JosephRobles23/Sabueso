"use client";

/**
 * DirectorMode — overlay oculto que controla el replay. Se activa con
 * Cmd+Opt+D (Ctrl+Alt+D en no-Mac). Sólo se monta cuando el shell está en
 * `mode=replay`; el listener de teclado se registra y se limpia en el mismo
 * effect para no fugarse en sesiones live.
 *
 * Controles visibles cuando el overlay está abierto:
 *   - Play/Pause
 *   - Forward (saltar al próximo evento — útil para "saltar el lento")
 *   - End (saltar al último evento — para mostrar el estado final inmediato)
 *   - Slider de timeline (drag → seek)
 *   - Cmd+Opt+D para cerrar
 */
import * as React from "react";
import {
  ChevronsRight,
  FastForward,
  Pause,
  Play,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import type { ReplayControls } from "@/hooks/useInvestigation";

export interface DirectorModeProps {
  controls: ReplayControls;
}

export function DirectorMode({ controls }: DirectorModeProps) {
  const [open, setOpen] = React.useState(false);

  // Cmd+Opt+D toggle. Listener montado/desmontado con el componente — por
  // construcción sólo existe cuando el shell está en mode=replay.
  React.useEffect(() => {
    function onKey(e: KeyboardEvent) {
      // d/D + alt (Opt en Mac) + meta (Cmd Mac) o ctrl (Windows/Linux)
      const isD = e.key.toLowerCase() === "d";
      const altOk = e.altKey;
      const modOk = e.metaKey || e.ctrlKey;
      if (isD && altOk && modOk) {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  if (!open) {
    // Sigue presente en el DOM para que el shortcut funcione, pero invisible.
    return <div aria-hidden className="sr-only" data-director="closed" />;
  }

  const snap = controls.snapshot;
  const playing = snap.status === "playing";
  const ended = snap.status === "ended";
  const pct = snap.durationMs > 0 ? Math.min(100, (snap.elapsedMs / snap.durationMs) * 100) : 0;

  return (
    <div
      role="dialog"
      aria-label="Director mode"
      className="fixed inset-x-4 bottom-4 z-50 mx-auto flex max-w-2xl flex-col gap-3 rounded-[var(--radius-lg)] border border-[var(--color-border-strong)] bg-[var(--color-surface)] p-4 shadow-2xl backdrop-blur"
    >
      <div className="flex items-baseline justify-between">
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-[10px] uppercase tracking-wider text-[var(--color-accent)]">
            Director
          </span>
          <span className="font-mono text-[11px] uppercase tracking-wider text-[var(--color-text-muted)]">
            {snap.currentIndex + 1} / {snap.totalEvents} · {snap.status}
          </span>
        </div>
        <button
          type="button"
          aria-label="Cerrar Director"
          onClick={() => setOpen(false)}
          className="rounded-[var(--radius-sm)] p-1 text-[var(--color-text-muted)] hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text-primary)]"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <input
        type="range"
        min={0}
        max={snap.durationMs}
        step={50}
        value={Math.round(snap.elapsedMs)}
        onChange={(e) => controls.seek(Number(e.target.value))}
        aria-label="Timeline"
        className="director-slider w-full accent-[var(--color-accent)]"
      />

      <div className="flex items-center justify-between gap-2">
        <div className="font-mono text-[11px] tabular-nums text-[var(--color-text-secondary)]">
          {formatMs(snap.elapsedMs)} / {formatMs(snap.durationMs)}
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            aria-label={playing ? "Pausar" : "Reproducir"}
            onClick={() => (playing ? controls.pause() : controls.play())}
            disabled={ended}
          >
            {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            aria-label="Próximo evento"
            onClick={() => controls.next()}
            disabled={ended}
          >
            <FastForward className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            aria-label="Saltar al final"
            onClick={() => controls.end()}
            disabled={ended}
          >
            <ChevronsRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <p className="font-mono text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
        Cmd+Opt+D para cerrar · cero llamadas externas activas
      </p>
    </div>
  );
}

function formatMs(ms: number): string {
  const total = Math.max(0, Math.round(ms / 1000));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}
