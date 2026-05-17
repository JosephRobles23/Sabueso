// Sabueso shared types — generated from Pydantic schemas + manual additions
// This file is the entry point for all types shared between frontend and backend

import type { EventType } from "./events";
export * from "./events";

export type Country = "pe" | "cl" | "mx" | "sv";
export type EntityType = "person" | "company" | "government_entity" | "contract";
export type InvestigationStatus =
  | "pending"
  | "planning"
  | "running"
  | "verifying"
  | "synthesizing"
  | "complete"
  | "failed"
  | "cancelled";

export type InvestigatorCallsign =
  | "sabueso"
  | "el-buscador"
  | "la-tasadora"
  | "el-contador"
  | "el-letrado"
  | "el-detective"
  | "el-periodista"
  | "la-jueza";

export type AgentStatus = "idle" | "thinking" | "working" | "blocked" | "done";

// EventType is re-exported from ./events (the canonical SSE event contract).

export interface Entity {
  id: string;
  country: Country;
  type: EntityType;
  identifier: string | null;
  name: string;
  aliases: string[];
  metadata: Record<string, unknown>;
}

export interface Claim {
  id: string;
  investigation_id: string;
  entity_id: string;
  predicate: string;
  object_value: Record<string, unknown>;
  source_url: string;
  source_extract: string | null;
  confidence: number;
  agent_callsign: InvestigatorCallsign;
  verified_by_jueza: boolean;
  created_at: string;
}

export interface Edge {
  id: string;
  from_entity: string;
  to_entity: string;
  type: string;
  weight: number;
  confidence: number;
  agent_callsign: InvestigatorCallsign | null;
}

export interface Investigation {
  id: string;
  target_entity_id: string;
  country: Country;
  locale: string;
  status: InvestigationStatus;
  plan: Array<{ agent: string; task: string; priority: number }>;
  dossier_md: string | null;
  cost_usd: number;
  progress_pct: number;
  is_public: boolean;
  started_at: string;
  finished_at: string | null;
}

export interface InvestigationEvent {
  id: number;
  investigation_id: string;
  type: EventType;
  agent_callsign: InvestigatorCallsign | null;
  payload: Record<string, unknown>;
  created_at: string;
}

// Investigator metadata for UI rendering
export interface InvestigatorProfile {
  callsign: InvestigatorCallsign;
  displayName: string;
  role: string;
  color: string;
  model: string;
  strategy: "rewoo" | "react";
}

export const INVESTIGATORS: InvestigatorProfile[] = [
  { callsign: "sabueso", displayName: "Sabueso", role: "Orchestrator", color: "#F59E0B", model: "claude-sonnet-4.6", strategy: "rewoo" },
  { callsign: "el-buscador", displayName: "El Buscador", role: "Recon", color: "#94A3B8", model: "kimi-k2.6", strategy: "rewoo" },
  { callsign: "la-tasadora", displayName: "La Tasadora", role: "Patrimony", color: "#34D399", model: "deepseek-v4-flash", strategy: "react" },
  { callsign: "el-contador", displayName: "El Contador", role: "Contracts", color: "#8B5CF6", model: "kimi-k2.6", strategy: "rewoo" },
  { callsign: "el-letrado", displayName: "El Letrado", role: "Legal", color: "#38BDF8", model: "deepseek-v4-flash", strategy: "rewoo" },
  { callsign: "el-detective", displayName: "El Detective", role: "Relationships", color: "#FB7185", model: "deepseek-v4-flash", strategy: "react" },
  { callsign: "el-periodista", displayName: "El Periodista", role: "News", color: "#FB923C", model: "kimi-k2.6", strategy: "react" },
  { callsign: "la-jueza", displayName: "La Jueza", role: "Verifier MoA", color: "#DC2626", model: "claude-sonnet-4.6", strategy: "rewoo" },
];
