"use client";

import { useEffect } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useInvestigation } from "@/hooks/useInvestigation";
import { useLocalStorageInvestigation } from "@/hooks/useLocalStorageInvestigation";
import { INVESTIGATORS } from "@sabueso/shared-types";

type Labels = {
  missionControl: string;
  investigationFloor: string;
  dossier: string;
  loadingPlan: string;
  loadingFloor: string;
  loadingDossier: string;
  preparing: string;
};

export function InvestigationShell({ id, labels }: { id: string; labels: Labels }) {
  const { hydrated, save } = useLocalStorageInvestigation(id);
  const { state, isLive } = useInvestigation(id, { initialState: hydrated });

  useEffect(() => {
    save?.(state);
  }, [state, save]);

  return (
    <main className="mx-auto flex w-full max-w-[1400px] flex-col gap-4 px-4 py-4 lg:px-6">
      <header className="flex items-center justify-between">
        <div className="space-y-1">
          <p className="font-mono text-[11px] uppercase tracking-wider text-[var(--color-text-muted)]">
            #INV-{id.slice(0, 8)}
          </p>
          <h1 className="font-display text-2xl tracking-tight">{labels.preparing}</h1>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span
            aria-label={isLive ? "live" : "offline"}
            className={
              "inline-block h-2 w-2 rounded-full " +
              (isLive ? "bg-[var(--color-declared)] animate-pulse-led" : "bg-[var(--color-text-muted)]")
            }
          />
          <span className="font-mono text-[var(--color-text-secondary)]">
            {Math.round(state.progress)}%
          </span>
        </div>
      </header>

      <div className="h-1 overflow-hidden rounded-full bg-[var(--color-surface-2)]">
        <div
          className="h-full bg-[var(--color-accent)] transition-[width] duration-500"
          style={{ width: `${Math.min(100, Math.max(0, state.progress))}%` }}
        />
      </div>

      <section
        aria-label="three-panel"
        className="grid flex-1 gap-4 lg:grid-cols-[28%_44%_28%]"
      >
        <PanelSkeleton title={labels.missionControl} helper={labels.loadingPlan} bars={6} />
        <PanelSkeleton title={labels.investigationFloor} helper={labels.loadingFloor} bars={10} dense />
        <PanelSkeleton title={labels.dossier} helper={labels.loadingDossier} bars={8} />
      </section>

      <section
        aria-label="operatives-floor"
        className="rounded-[var(--radius-lg)] border bg-[var(--color-surface-2)] p-4"
      >
        <ul className="flex gap-3 overflow-x-auto pb-1">
          {INVESTIGATORS.map((investigator) => {
            const agent = state.agents[investigator.callsign];
            const status = agent?.status ?? "idle";
            return (
              <li
                key={investigator.callsign}
                className="min-w-[110px] rounded-[var(--radius-md)] border border-[var(--color-border-default)] bg-[var(--color-surface)] p-3 text-center"
              >
                <span
                  className="mx-auto mb-2 block h-8 w-8 rounded-full"
                  style={{ background: investigator.color }}
                  aria-hidden
                />
                <p className="font-callsign text-sm leading-tight">{investigator.displayName}</p>
                <p className="mt-1 font-mono text-[10px] uppercase text-[var(--color-text-muted)]">
                  {status}
                </p>
              </li>
            );
          })}
        </ul>
      </section>
    </main>
  );
}

function PanelSkeleton({
  title,
  helper,
  bars,
  dense,
}: {
  title: string;
  helper: string;
  bars: number;
  dense?: boolean;
}) {
  return (
    <Card className="flex h-full flex-col">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <p className="text-xs text-[var(--color-text-secondary)]">{helper}</p>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-2">
        {Array.from({ length: bars }).map((_, index) => (
          <Skeleton
            key={index}
            className={dense ? "h-3 w-full" : index % 3 === 0 ? "h-4 w-4/5" : "h-3 w-full"}
          />
        ))}
      </CardContent>
    </Card>
  );
}
