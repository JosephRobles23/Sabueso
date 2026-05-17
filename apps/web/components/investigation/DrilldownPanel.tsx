"use client";

import * as React from "react";
import type { EventType, InvestigationEvent, InvestigatorCallsign } from "@sabueso/shared-types";
import { INVESTIGATORS } from "@sabueso/shared-types";

import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import type { AgentSnapshot } from "@/lib/mockInvestigationState";
import { cn } from "@/lib/utils";

import { InvestigatorAvatar } from "./InvestigatorAvatar";
import { StatusPill } from "./StatusPill";

const PROFILE_BY_CALLSIGN = new Map(INVESTIGATORS.map((i) => [i.callsign, i]));

export interface DrilldownPanelProps {
  /** Callsign whose drill-down to show. `null` closes the sheet. */
  callsign: InvestigatorCallsign | null;
  events: InvestigationEvent[];
  agents: Record<string, AgentSnapshot>;
  onOpenChange: (open: boolean) => void;
}

const EVENT_BORDER: Record<EventType, string> = {
  investigation_started: "var(--color-text-muted)",
  plan_generated: "var(--color-sabueso)",
  agent_started: "var(--color-discovered)",
  tool_call: "var(--color-text-secondary)",
  claim_created: "var(--color-declared)",
  edge_discovered: "var(--color-detective)",
  agent_finished: "var(--color-declared)",
  verification_done: "var(--color-jueza)",
  synthesis_started: "var(--color-accent)",
  investigation_complete: "var(--color-declared)",
  investigation_failed: "var(--color-suspicious)",
  heartbeat: "var(--color-text-muted)",
};

const EVENT_LABEL: Record<EventType, string> = {
  investigation_started: "investigación iniciada",
  plan_generated: "plan generado",
  agent_started: "agente iniciado",
  tool_call: "tool call",
  claim_created: "claim",
  edge_discovered: "relación",
  agent_finished: "agente cerró",
  verification_done: "verificación",
  synthesis_started: "síntesis",
  investigation_complete: "completa",
  investigation_failed: "falló",
  heartbeat: "heartbeat",
};

export function DrilldownPanel({ callsign, events, agents, onOpenChange }: DrilldownPanelProps) {
  const open = callsign !== null;
  const profile = callsign ? PROFILE_BY_CALLSIGN.get(callsign) : undefined;
  const agent = callsign ? agents[callsign] : undefined;

  // Filtered timeline. Reverse-chrono so most recent is on top.
  const timeline = React.useMemo(() => {
    if (!callsign) return [];
    return events
      .filter((e) => e.agent_callsign === callsign)
      .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
  }, [events, callsign]);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:w-[440px]">
        {profile && callsign ? (
          <>
            <SheetHeader>
              <div className="flex items-center gap-3">
                <InvestigatorAvatar
                  callsign={callsign}
                  size={64}
                  state={agent?.status === "blocked" ? "error" : "active"}
                />
                <div className="min-w-0">
                  <SheetTitle style={{ color: profile.color }}>{profile.displayName}</SheetTitle>
                  <SheetDescription>
                    {profile.role} · {profile.model}
                  </SheetDescription>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <StatusPill status={agent?.status ?? "idle"} detail={agent?.detail} />
                <span className="font-mono text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
                  {profile.strategy.toUpperCase()}
                </span>
              </div>
            </SheetHeader>

            {agent?.currentLead ? (
              <section
                aria-label="Pista en curso"
                className="rounded-[var(--radius-md)] border border-dashed bg-[var(--color-surface-2)] p-3"
              >
                <p className="mb-1 font-mono text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
                  Pista en curso
                </p>
                <p className="text-sm leading-snug text-[var(--color-text-primary)]">
                  {agent.currentLead}
                </p>
              </section>
            ) : null}

            <section
              aria-label="Activity timeline"
              className="flex min-h-0 flex-1 flex-col overflow-hidden"
            >
              <header className="mb-2 flex items-center justify-between">
                <p className="font-mono text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
                  Activity timeline
                </p>
                <span className="font-mono text-[10px] text-[var(--color-text-muted)]">
                  {timeline.length} eventos
                </span>
              </header>

              <ol
                aria-live="polite"
                className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto pr-1"
              >
                {timeline.length === 0 ? (
                  <li className="rounded-[var(--radius-sm)] border border-dashed p-3 text-center font-mono text-[10px] text-[var(--color-text-muted)]">
                    Sin actividad todavía
                  </li>
                ) : (
                  timeline.map((e) => (
                    <li
                      key={e.id}
                      className={cn(
                        "rounded-[var(--radius-sm)] border-l-2 bg-[var(--color-surface-2)] px-3 py-2",
                      )}
                      style={{ borderLeftColor: EVENT_BORDER[e.type] }}
                    >
                      <div className="mb-1 flex items-baseline justify-between gap-2">
                        <span
                          className="font-mono text-[10px] uppercase tracking-wider"
                          style={{ color: EVENT_BORDER[e.type] }}
                        >
                          {EVENT_LABEL[e.type]}
                        </span>
                        <time className="font-mono text-[10px] text-[var(--color-text-muted)]">
                          {formatTime(e.created_at)}
                        </time>
                      </div>
                      <EventBody event={e} />
                    </li>
                  ))
                )}
              </ol>
            </section>
          </>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}

function EventBody({ event }: { event: InvestigationEvent }) {
  const p = event.payload as Record<string, unknown> | null;
  if (!p) return null;
  switch (event.type) {
    case "tool_call":
      return (
        <p className="font-mono text-[11px] text-[var(--color-text-secondary)]">
          {String(p.tool ?? "tool")}
          {typeof p.duration_ms === "number" ? ` · ${p.duration_ms}ms` : ""}
        </p>
      );
    case "claim_created":
      return (
        <p className="text-xs text-[var(--color-text-primary)]">
          {String(p.predicate ?? "claim")}{" "}
          {typeof p.confidence === "number" ? (
            <span className="font-mono text-[10px] text-[var(--color-text-muted)]">
              · conf {(p.confidence as number).toFixed(2)}
            </span>
          ) : null}
        </p>
      );
    case "agent_started":
      return (
        <p className="text-xs text-[var(--color-text-primary)]">
          {String(p.task ?? "tarea")}
        </p>
      );
    case "agent_finished":
      return (
        <p className="font-mono text-[11px] text-[var(--color-text-secondary)]">
          {String(p.claims_created ?? 0)} claims · ${(Number(p.cost_usd) || 0).toFixed(2)}
        </p>
      );
    case "edge_discovered":
      return (
        <p className="font-mono text-[11px] text-[var(--color-text-secondary)]">
          {String(p.from_entity ?? "?")} → {String(p.to_entity ?? "?")}
        </p>
      );
    default:
      return null;
  }
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString("es-PE", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return "";
  }
}
