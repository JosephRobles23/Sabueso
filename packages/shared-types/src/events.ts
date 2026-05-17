// AUTO-GENERATED from apps/worker/src/events/schemas.py (S-08).
// Regenerate with:
//   cd packages/shared-types && pnpm run generate:events
// (calls pydantic-to-typescript against apps/worker/src/events/schemas.py)
//
// Until that script runs in CI, this file is the contract — keep it in sync
// with the Pydantic models by hand if you tweak schemas before regenerating.

import type { Country, InvestigatorCallsign } from "./index";

export type EventType =
  | "investigation_started"
  | "plan_generated"
  | "agent_started"
  | "tool_call"
  | "claim_created"
  | "edge_discovered"
  | "agent_finished"
  | "verification_done"
  | "synthesis_started"
  | "investigation_complete"
  | "investigation_failed"
  | "heartbeat"

export const TERMINAL_EVENT_TYPES = [
  "investigation_complete",
  "investigation_failed",
] as const

export type TerminalEventType = (typeof TERMINAL_EVENT_TYPES)[number]

export interface PlanStep {
  agent: InvestigatorCallsign
  task: string
  priority: number
}

export interface InvestigationStartedPayload {
  type: "investigation_started"
  investigation_id: string
  entity_id: string
  country: Country
  locale: string
}

export interface PlanGeneratedPayload {
  type: "plan_generated"
  plan: PlanStep[]
}

export interface AgentStartedPayload {
  type: "agent_started"
  agent: InvestigatorCallsign
  task: string
}

export interface ToolCallPayload {
  type: "tool_call"
  agent: InvestigatorCallsign
  tool: string
  args: Record<string, unknown>
  cache_hit: boolean
  duration_ms: number | null
}

export interface ClaimCreatedPayload {
  type: "claim_created"
  claim_id: string
  entity_id: string
  predicate: string
  object_value: Record<string, unknown>
  source_url: string
  confidence: number
  agent: InvestigatorCallsign
}

export interface EdgeDiscoveredPayload {
  type: "edge_discovered"
  edge_id: string
  from_entity: string
  to_entity: string
  edge_type: string
  weight: number
  confidence: number
  agent: InvestigatorCallsign | null
}

export interface AgentFinishedPayload {
  type: "agent_finished"
  agent: InvestigatorCallsign
  claims_created: number
  cost_usd: number
  duration_ms: number
}

export interface VerificationDonePayload {
  type: "verification_done"
  claim_id: string
  verified: boolean
  verifier_score: number
  notes: string | null
}

export interface SynthesisStartedPayload {
  type: "synthesis_started"
  claim_count: number
}

export interface InvestigationCompletePayload {
  type: "investigation_complete"
  dossier_url: string | null
  total_claims: number
  total_cost_usd: number
  duration_ms: number
}

export interface InvestigationFailedPayload {
  type: "investigation_failed"
  error: string
  failed_agent: InvestigatorCallsign | null
  partial_claims: number
}

export interface HeartbeatPayload {
  type: "heartbeat"
  ts: string
}

export type EventPayload =
  | InvestigationStartedPayload
  | PlanGeneratedPayload
  | AgentStartedPayload
  | ToolCallPayload
  | ClaimCreatedPayload
  | EdgeDiscoveredPayload
  | AgentFinishedPayload
  | VerificationDonePayload
  | SynthesisStartedPayload
  | InvestigationCompletePayload
  | InvestigationFailedPayload
  | HeartbeatPayload

// SSE wire envelope — what the EventSource ``message`` callback receives in
// ``event.data`` after JSON.parse. ``id`` is the BIGSERIAL id and ``event``
// is the EventType (mirrors the SSE ``id:`` / ``event:`` lines).
export interface StreamedEvent {
  id: number
  investigation_id: string
  type: EventType
  agent_callsign: InvestigatorCallsign | null
  payload: EventPayload
  created_at: string
}

export type PayloadByType = {
  investigation_started: InvestigationStartedPayload
  plan_generated: PlanGeneratedPayload
  agent_started: AgentStartedPayload
  tool_call: ToolCallPayload
  claim_created: ClaimCreatedPayload
  edge_discovered: EdgeDiscoveredPayload
  agent_finished: AgentFinishedPayload
  verification_done: VerificationDonePayload
  synthesis_started: SynthesisStartedPayload
  investigation_complete: InvestigationCompletePayload
  investigation_failed: InvestigationFailedPayload
  heartbeat: HeartbeatPayload
}
