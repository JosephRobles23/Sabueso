"use client";

import * as React from "react";
import type {
  Claim,
  InvestigationEvent,
  InvestigatorCallsign,
  PlanStep,
  ToolCallPayload,
} from "@sabueso/shared-types";
import { INVESTIGATORS } from "@sabueso/shared-types";

import {
  Conversation,
  Message,
  Reasoning,
  Source,
  Response,
  Tool,
} from "@/components/ai-elements";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { AgentSnapshot } from "@/lib/mockInvestigationState";
import { cn } from "@/lib/utils";

import { ConfidenceBadge } from "./ConfidenceBadge";
import { EvidenceChip, type EvidenceSourceType } from "./EvidenceChip";
import { InvestigatorAvatar } from "./InvestigatorAvatar";
import { StatusPill } from "./StatusPill";

export interface MissionControlProps {
  plan: PlanStep[];
  agents: Record<string, AgentSnapshot>;
  events: InvestigationEvent[];
  claims: Claim[];
  className?: string;
}

const PROFILE_BY_CALLSIGN = new Map(INVESTIGATORS.map((i) => [i.callsign, i]));

export function MissionControl({
  plan,
  agents,
  events,
  claims,
  className,
}: MissionControlProps) {
  return (
    <section
      aria-label="Mission Control"
      className={cn(
        "flex h-full min-h-0 flex-col rounded-[var(--radius-lg)] border bg-[var(--color-surface)]",
        className,
      )}
    >
      <header className="flex items-baseline justify-between border-b border-[var(--color-border-default)] px-4 py-3">
        <h2 className="font-display text-lg">Mission Control</h2>
        <span className="font-mono text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
          {events.length} eventos
        </span>
      </header>

      <Tabs defaultValue="chat" className="flex min-h-0 flex-1 flex-col">
        <div className="px-4 pt-3">
          <TabsList className="w-full">
            <TabsTrigger value="chat" className="flex-1">
              Chat
            </TabsTrigger>
            <TabsTrigger value="pistas" className="flex-1">
              Pistas
            </TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="chat" className="min-h-0 flex-1 overflow-hidden px-3 pb-3">
          <ChatStream plan={plan} events={events} claims={claims} />
        </TabsContent>

        <TabsContent value="pistas" className="min-h-0 flex-1 overflow-y-auto px-3 pb-3">
          <PistasKanban plan={plan} agents={agents} />
        </TabsContent>
      </Tabs>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Chat stream
// ─────────────────────────────────────────────────────────────────────────────

function ChatStream({
  plan,
  events,
  claims,
}: {
  plan: PlanStep[];
  events: InvestigationEvent[];
  claims: Claim[];
}) {
  const claimById = React.useMemo(() => {
    const map = new Map<string, Claim>();
    for (const c of claims) map.set(c.id, c);
    return map;
  }, [claims]);

  return (
    <Conversation className="h-full">
      {/* Sabueso's plan as a Reasoning block at the top of the conversation. */}
      <Message
        from="agent"
        author="Sabueso"
        accentColor={PROFILE_BY_CALLSIGN.get("sabueso")?.color}
        avatar={<InvestigatorAvatar callsign="sabueso" size={48} state="active" />}
        timestamp="13:55"
      >
        <Response>
          He generado el plan. Voy a delegar a los 7 investigadores en paralelo y
          consolidar findings vía La Jueza.
        </Response>
        <div className="mt-2">
          <Reasoning title={`Plan (${plan.length} pasos)`} defaultOpen>
            <ol className="list-decimal space-y-1 pl-4">
              {plan.map((p, i) => (
                <li key={i}>
                  <span className="font-callsign">
                    {PROFILE_BY_CALLSIGN.get(p.agent)?.displayName ?? p.agent}
                  </span>{" "}
                  · {p.task}
                </li>
              ))}
            </ol>
          </Reasoning>
        </div>
      </Message>

      {events.map((e) => renderEvent(e, claimById))}
    </Conversation>
  );
}

function renderEvent(e: InvestigationEvent, claimById: Map<string, Claim>) {
  const callsign = e.agent_callsign;
  const profile = callsign ? PROFILE_BY_CALLSIGN.get(callsign) : undefined;
  const accent = profile?.color;
  const time = formatTime(e.created_at);

  switch (e.type) {
    case "agent_started": {
      const task = (e.payload as { task?: string } | null)?.task ?? "Tarea asignada";
      if (!callsign) return null;
      return (
        <Message
          key={e.id}
          from="agent"
          author={profile?.displayName}
          accentColor={accent}
          avatar={<InvestigatorAvatar callsign={callsign} size={48} state="active" />}
          timestamp={time}
        >
          <Response>
            <span className="text-[var(--color-text-secondary)]">▶</span> {task}
          </Response>
        </Message>
      );
    }
    case "tool_call": {
      const payload = e.payload as unknown as ToolCallPayload;
      if (!callsign) return null;
      return (
        <Message
          key={e.id}
          from="agent"
          author={profile?.displayName}
          accentColor={accent}
          avatar={<InvestigatorAvatar callsign={callsign} size={48} />}
          timestamp={time}
        >
          <Tool
            name={payload.tool}
            status={payload.cache_hit ? "cache_hit" : "ok"}
            durationMs={payload.duration_ms ?? null}
            args={payload.args}
          />
        </Message>
      );
    }
    case "claim_created": {
      const payload = e.payload as {
        claim_id?: string;
        confidence?: number;
        predicate?: string;
      } | null;
      const claim = payload?.claim_id ? claimById.get(payload.claim_id) : undefined;
      const confidence = claim?.confidence ?? payload?.confidence ?? 0;
      const predicate = claim?.predicate ?? payload?.predicate ?? "claim";
      if (!callsign) return null;
      return (
        <Message
          key={e.id}
          from="agent"
          author={profile?.displayName}
          accentColor={accent}
          avatar={<InvestigatorAvatar callsign={callsign} size={48} />}
          timestamp={time}
        >
          <Response>
            <span className="font-mono text-[11px] uppercase tracking-wider text-[var(--color-text-muted)]">
              hallazgo
            </span>{" "}
            <span className="text-[var(--color-text-primary)]">{predicate}</span>
          </Response>
          {claim?.source_extract ? (
            <p className="mt-1 text-xs italic text-[var(--color-text-secondary)]">
              “{claim.source_extract}”
            </p>
          ) : null}
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <ConfidenceBadge value={confidence} />
            {claim?.source_url ? (
              <Source>
                <EvidenceChip
                  sourceUrl={claim.source_url}
                  sourceType={detectSourceType(claim.source_url)}
                />
              </Source>
            ) : null}
          </div>
        </Message>
      );
    }
    case "agent_finished": {
      const payload = e.payload as { claims_created?: number; cost_usd?: number } | null;
      if (!callsign) return null;
      return (
        <Message
          key={e.id}
          from="system"
          author={profile?.displayName}
          accentColor={accent}
          avatar={<InvestigatorAvatar callsign={callsign} size={48} />}
          timestamp={time}
        >
          <Response>
            <span className="font-mono text-[11px] uppercase tracking-wider text-[var(--color-text-muted)]">
              cerrado
            </span>{" "}
            {payload?.claims_created ?? 0} claims · $
            {(payload?.cost_usd ?? 0).toFixed(2)}
          </Response>
        </Message>
      );
    }
    case "edge_discovered": {
      const payload = e.payload as { from_entity?: string; to_entity?: string } | null;
      return (
        <Message
          key={e.id}
          from="system"
          author={profile?.displayName ?? "Detective"}
          accentColor={accent ?? "var(--color-discovered)"}
          avatar={callsign ? <InvestigatorAvatar callsign={callsign} size={48} /> : undefined}
          timestamp={time}
        >
          <Response>
            <span className="font-mono text-[11px] uppercase tracking-wider text-[var(--color-text-muted)]">
              relación
            </span>{" "}
            {payload?.from_entity} → {payload?.to_entity}
          </Response>
        </Message>
      );
    }
    case "plan_generated":
    case "investigation_started":
    case "heartbeat":
      return null;
    default:
      return null;
  }
}

function detectSourceType(url: string): EvidenceSourceType {
  if (/jne\.gob\.pe/i.test(url)) return "jne";
  if (/seace\.gob\.pe/i.test(url)) return "seace";
  if (/sunarp\.gob\.pe/i.test(url)) return "sunarp";
  if (/legalize/i.test(url)) return "legalize";
  if (/elcomercio|gestion|larepublica|peru21/i.test(url)) return "news";
  return "other";
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString("es-PE", {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Pistas — kanban
// ─────────────────────────────────────────────────────────────────────────────

type Column = "por_asignar" | "listas" | "en_curso" | "cerradas";

const COLUMNS: Array<{ id: Column; label: string; tint: string }> = [
  { id: "por_asignar", label: "Por asignar", tint: "var(--color-text-muted)" },
  { id: "listas", label: "Listas", tint: "var(--color-ambiguous)" },
  { id: "en_curso", label: "En curso", tint: "var(--color-discovered)" },
  { id: "cerradas", label: "Cerradas", tint: "var(--color-declared)" },
];

function bucketFor(status: AgentSnapshot["status"]): Column {
  switch (status) {
    case "idle":
      return "por_asignar";
    case "thinking":
      return "listas";
    case "working":
      return "en_curso";
    case "blocked":
      return "en_curso";
    case "done":
      return "cerradas";
    default:
      return "por_asignar";
  }
}

function PistasKanban({
  plan,
  agents,
}: {
  plan: PlanStep[];
  agents: Record<string, AgentSnapshot>;
}) {
  const cards = React.useMemo(
    () =>
      plan.map((p) => {
        const snap = agents[p.agent];
        const status = snap?.status ?? "idle";
        return {
          plan: p,
          status,
          detail: snap?.detail,
          bucket: bucketFor(status),
        };
      }),
    [plan, agents],
  );

  return (
    <div
      role="list"
      aria-label="Pistas (kanban)"
      className="grid h-full auto-rows-min grid-cols-2 gap-2"
    >
      {COLUMNS.map((col) => {
        const items = cards.filter((c) => c.bucket === col.id);
        return (
          <div
            key={col.id}
            role="listitem"
            className="flex flex-col gap-1.5 rounded-[var(--radius-md)] border bg-[var(--color-surface-2)] p-2"
          >
            <header className="flex items-center justify-between px-1 pb-1">
              <span
                className="inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider"
                style={{ color: col.tint }}
              >
                <span
                  aria-hidden
                  className="h-1.5 w-1.5 rounded-full"
                  style={{ backgroundColor: col.tint }}
                />
                {col.label}
              </span>
              <span className="font-mono text-[10px] text-[var(--color-text-muted)]">
                {items.length}
              </span>
            </header>

            <ul className="flex flex-col gap-2">
              {items.length === 0 ? (
                <li className="py-4 text-center font-mono text-[10px] text-[var(--color-text-muted)]">
                  —
                </li>
              ) : (
                items.map((c, i) => {
                  const profile = PROFILE_BY_CALLSIGN.get(c.plan.agent as InvestigatorCallsign);
                  return (
                    <li
                      key={`${c.plan.agent}-${i}`}
                      className="rounded-[var(--radius-sm)] border bg-[var(--color-surface)] p-2 text-xs"
                      style={{
                        borderLeftColor: profile?.color ?? "var(--color-accent)",
                        borderLeftWidth: 3,
                      }}
                    >
                      <div className="mb-1 flex items-center justify-between">
                        <span
                          className="font-callsign text-[12px]"
                          style={{ color: profile?.color }}
                        >
                          {profile?.displayName ?? c.plan.agent}
                        </span>
                        <StatusPill status={c.status} />
                      </div>
                      <p className="text-[12px] leading-snug text-[var(--color-text-primary)]">
                        {c.plan.task}
                      </p>
                      {c.detail ? (
                        <p className="mt-1 font-mono text-[10px] text-[var(--color-text-muted)]">
                          {c.detail}
                        </p>
                      ) : null}
                    </li>
                  );
                })
              )}
            </ul>
          </div>
        );
      })}
    </div>
  );
}
