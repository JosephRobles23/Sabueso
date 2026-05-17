import type { AgentStatus, InvestigatorCallsign } from "@sabueso/shared-types";
import { INVESTIGATORS } from "@sabueso/shared-types";

export type InvestigationStatusMeta = {
  label: string;
  color: string;
  dotPulse?: boolean;
};

export const STATUS_META: Record<AgentStatus, InvestigationStatusMeta> = {
  idle: { label: "En espera", color: "var(--color-text-muted)" },
  thinking: { label: "Pensando", color: "var(--color-ambiguous)", dotPulse: true },
  working: { label: "Trabajando", color: "var(--color-discovered)" },
  blocked: { label: "Bloqueado", color: "var(--color-suspicious)" },
  done: { label: "Cerrado", color: "var(--color-declared)" },
};

const PROFILE_BY_CALLSIGN = new Map(INVESTIGATORS.map((i) => [i.callsign, i]));

export function callsignColor(callsign: InvestigatorCallsign): string {
  return PROFILE_BY_CALLSIGN.get(callsign)?.color ?? "var(--color-accent)";
}

export function callsignDisplayName(callsign: InvestigatorCallsign): string {
  return PROFILE_BY_CALLSIGN.get(callsign)?.displayName ?? callsign;
}

export function callsignRole(callsign: InvestigatorCallsign): string {
  return PROFILE_BY_CALLSIGN.get(callsign)?.role ?? "";
}
