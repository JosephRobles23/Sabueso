"use client";

import { createClient } from "@/lib/supabase/client";
import type { EventType, InvestigationEvent, InvestigatorCallsign } from "@sabueso/shared-types";

/**
 * Trae todos los eventos de una investigación cacheada, ordenados por id
 * ascendente. Lee directo de Supabase con el browser client; las rows
 * deben ser legibles por la RLS pública (investigations.is_public = true
 * para los demos cacheados).
 *
 * Devuelve un array vacío si la investigación no existe o RLS lo bloquea
 * — el consumidor debe interpretar eso como "no hay nada para reproducir".
 */
export async function fetchReplayEvents(investigationId: string): Promise<InvestigationEvent[]> {
  const supabase = createClient();
  if (!supabase) return [];

  const { data, error } = await supabase
    .from("investigation_events")
    .select("id, investigation_id, type, agent_callsign, payload, created_at")
    .eq("investigation_id", investigationId)
    .order("id", { ascending: true });

  if (error || !data) return [];

  return data.map((row) => ({
    id: Number(row.id),
    investigation_id: String(row.investigation_id),
    type: row.type as EventType,
    agent_callsign: (row.agent_callsign as InvestigatorCallsign | null) ?? null,
    payload: (row.payload as Record<string, unknown> | null) ?? {},
    created_at: String(row.created_at),
  }));
}
