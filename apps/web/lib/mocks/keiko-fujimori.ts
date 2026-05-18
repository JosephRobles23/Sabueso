import type { Claim, InvestigationEvent, InvestigatorCallsign, PlanStep } from "@sabueso/shared-types"
import type {
  ActiveDelegation,
  AgentSnapshot,
  ComposedInvestigationState,
  GraphEdge,
  GraphEntity,
} from "@/lib/mockInvestigationState"

const INV_ID = "demo-keiko-fujimori"
const TARGET_NAME = "Keiko Fujimori Higuchi"
const TARGET_ID = "ent-keiko"

const PLAN: PlanStep[] = [
  { agent: "el-buscador", task: "Localizar DNI, RUC de Fuerza Popular y hoja de vida JNE 2021", priority: 1 },
  { agent: "el-contador", task: "Auditar declaraciones de financiamiento ONPE 2011 y 2016", priority: 1 },
  { agent: "el-detective", task: "Mapear red de aportantes, intermediarios y cuentas del partido", priority: 2 },
  { agent: "la-tasadora", task: "Cruzar aportes declarados vs. flujos bancarios reales (SBS/UIF)", priority: 2 },
  { agent: "el-letrado", task: "Revisar expedientes judiciales Caso Cócteles y lavado de activos", priority: 3 },
  { agent: "el-periodista", task: "Recopilar investigaciones de IDL-Reporteros, Ojo Público y El Comercio", priority: 4 },
  { agent: "la-jueza", task: "Verificar claims clave con score ≥ 0.6 vía Mixture-of-Agents", priority: 5 },
]

const AGENTS: Record<string, AgentSnapshot> = {
  sabueso: { callsign: "sabueso", status: "done", detail: "Investigación completada" },
  "el-buscador": { callsign: "el-buscador", status: "done", detail: "DNI + hoja de vida JNE ubicados" },
  "el-contador": { callsign: "el-contador", status: "done", detail: "5 discrepancias ONPE detectadas" },
  "el-detective": { callsign: "el-detective", status: "done", detail: "Red de 8 aportantes mapeada" },
  "la-tasadora": { callsign: "la-tasadora", status: "done", detail: "S/. 3.6M sin sustento en declaraciones" },
  "el-letrado": { callsign: "el-letrado", status: "done", detail: "Expediente 00299-2017 · lavado de activos" },
  "el-periodista": { callsign: "el-periodista", status: "done", detail: "42 notas relevantes recopiladas" },
  "la-jueza": { callsign: "la-jueza", status: "done", detail: "6/8 claims verificados ≥ 0.7" },
}

const ENTITIES: GraphEntity[] = [
  { id: TARGET_ID, name: TARGET_NAME, type: "person", semantic: "verified" },
  { id: "ent-fp", name: "Fuerza Popular", type: "company", semantic: "declared" },
  { id: "ent-odebrecht", name: "Odebrecht (Perú)", type: "company", semantic: "suspicious" },
  { id: "ent-yoshiyama", name: "Jaime Yoshiyama Tanaka", type: "person", semantic: "suspicious" },
  { id: "ent-romero", name: "Dionisio Romero Paoletti", type: "person", semantic: "discovered" },
  { id: "ent-cocktail", name: "Eventos de Recaudación (Cócteles)", type: "company", semantic: "ambiguous" },
  { id: "ent-onpe-2011", name: "Declaración ONPE 2011", type: "contract", semantic: "conflict" },
  { id: "ent-onpe-2016", name: "Declaración ONPE 2016", type: "contract", semantic: "conflict" },
  { id: "ent-exp-judicial", name: "Exp. 00299-2017 (Lavado de activos)", type: "government_entity", semantic: "verified" },
  { id: "ent-heredia", name: "Vicente Silva Checa", type: "person", semantic: "discovered" },
]

const EDGES: GraphEdge[] = [
  {
    id: "edg-k1", from: TARGET_ID, to: "ent-fp",
    type: "lidera", confidence: 0.99, weight: 1, semantic: "declared",
    occurred_at: "2010-06-15",
  },
  {
    id: "edg-k2", from: TARGET_ID, to: "ent-yoshiyama",
    type: "coordinador-campaña", confidence: 0.96, weight: 1, semantic: "verified",
    occurred_at: "2011-02-01",
  },
  {
    id: "edg-k3", from: "ent-yoshiyama", to: "ent-odebrecht",
    type: "recibió-fondos", confidence: 0.91, weight: 3.0, semantic: "suspicious",
    occurred_at: "2011-04-20",
    metadata: { amount_usd: 1_000_000, is_relative: false },
  },
  {
    id: "edg-k4", from: "ent-odebrecht", to: "ent-fp",
    type: "aporte-no-declarado", confidence: 0.88, weight: 3.6, semantic: "suspicious",
    occurred_at: "2011-05-10",
    metadata: { amount_usd: 1_200_000, is_relative: false },
  },
  {
    id: "edg-k5", from: "ent-fp", to: "ent-cocktail",
    type: "financiamiento-eventos", confidence: 0.82, weight: 2.0, semantic: "ambiguous",
    occurred_at: "2015-09-15",
    metadata: { amount_pen: 2_400_000, is_relative: false },
  },
  {
    id: "edg-k6", from: "ent-romero", to: "ent-fp",
    type: "aporte-encubierto", confidence: 0.85, weight: 1.5, semantic: "discovered",
    occurred_at: "2011-03-28",
    metadata: { amount_usd: 3_650_000, is_relative: false },
  },
  {
    id: "edg-k7", from: TARGET_ID, to: "ent-onpe-2011",
    type: "declaró-aportes", confidence: 0.98, weight: 1, semantic: "conflict",
    occurred_at: "2011-12-01",
  },
  {
    id: "edg-k8", from: TARGET_ID, to: "ent-onpe-2016",
    type: "declaró-aportes", confidence: 0.97, weight: 1, semantic: "conflict",
    occurred_at: "2016-11-15",
  },
  {
    id: "edg-k9", from: TARGET_ID, to: "ent-exp-judicial",
    type: "investigada", confidence: 0.99, weight: 1, semantic: "verified",
    occurred_at: "2017-10-10",
  },
  {
    id: "edg-k10", from: "ent-heredia", to: "ent-cocktail",
    type: "organizador", confidence: 0.74, weight: 0.8, semantic: "discovered",
    occurred_at: "2015-07-01",
  },
  {
    id: "edg-k11", from: "ent-romero", to: "ent-yoshiyama",
    type: "intermedió-entrega", confidence: 0.79, weight: 1.2, semantic: "suspicious",
    occurred_at: "2011-03-15",
    metadata: { amount_usd: 3_650_000, is_relative: false },
  },
]

const CLAIMS: Claim[] = [
  {
    id: "clm-k1", investigation_id: INV_ID, entity_id: TARGET_ID,
    predicate: "Candidata presidencial registrada en JNE",
    object_value: { dni: "25209800", partido: "Fuerza Popular" },
    source_url: "https://plataformaelectoral.jne.gob.pe/Candidato/HojaVida/25209800",
    source_extract: "Hoja de vida de candidata inscrita ante el JNE para las elecciones generales 2011 y 2021.",
    confidence: 0.99, agent_callsign: "el-buscador", verified_by_jueza: true,
    created_at: "2026-05-17T10:01:20Z",
  },
  {
    id: "clm-k2", investigation_id: INV_ID, entity_id: "ent-odebrecht",
    predicate: "Aporte de Odebrecht no declarado ante ONPE",
    object_value: { amount_usd: 1_000_000, destinatario: "Campaña 2011", via: "Jaime Yoshiyama" },
    source_url: "https://www.idl-reporteros.pe/odebrecht-keiko-fujimori/",
    source_extract: "Marcelo Odebrecht declaró ante fiscalía brasileña haber entregado US$ 1 millón a la campaña de Keiko Fujimori en 2011 a través de Jaime Yoshiyama.",
    confidence: 0.91, agent_callsign: "el-contador", verified_by_jueza: true,
    created_at: "2026-05-17T10:04:35Z",
  },
  {
    id: "clm-k3", investigation_id: INV_ID, entity_id: "ent-romero",
    predicate: "Aporte encubierto de Dionisio Romero",
    object_value: { amount_usd: 3_650_000, año: 2011, mecanismo: "pitufeo vía 32 falsos aportantes" },
    source_url: "https://ojo-publico.com/caso-cocteles-romero-paoletti/",
    source_extract: "Romero Paoletti admitió en juicio oral haber entregado US$ 3.65 millones a la campaña de 2011 de Fuerza Popular, fraccionados entre decenas de personas para evadir el límite legal de aportes individuales.",
    confidence: 0.88, agent_callsign: "el-detective", verified_by_jueza: true,
    created_at: "2026-05-17T10:08:12Z",
  },
  {
    id: "clm-k4", investigation_id: INV_ID, entity_id: "ent-onpe-2011",
    predicate: "Declaración de aportes 2011 incompleta",
    object_value: { declarado_pen: 1_200_000, estimado_real_pen: 14_400_000, diferencia_pen: 13_200_000 },
    source_url: "https://www.web.onpe.gob.pe/modFinanciamientoPP/consulta/2011",
    source_extract: "La declaración de Fuerza Popular ante ONPE reportó S/. 1.2M en aportes para la campaña 2011, pero investigaciones fiscales estiman flujos reales superiores a S/. 14M.",
    confidence: 0.84, agent_callsign: "la-tasadora", verified_by_jueza: true,
    created_at: "2026-05-17T10:12:45Z",
  },
  {
    id: "clm-k5", investigation_id: INV_ID, entity_id: "ent-exp-judicial",
    predicate: "Proceso penal por lavado de activos",
    object_value: { expediente: "00299-2017", juzgado: "Corte Suprema de Justicia", delitos: ["lavado de activos", "organización criminal"] },
    source_url: "https://cej.pj.gob.pe/cej/forms/detalleform.html?00299-2017",
    source_extract: "La Fiscalía acusó a Keiko Fujimori como presunta líder de una organización criminal al interior de Fuerza Popular dedicada al lavado de activos provenientes de fuentes ilícitas para financiar campañas electorales.",
    confidence: 0.93, agent_callsign: "el-letrado", verified_by_jueza: true,
    created_at: "2026-05-17T10:16:30Z",
  },
  {
    id: "clm-k6", investigation_id: INV_ID, entity_id: "ent-cocktail",
    predicate: "Cócteles de recaudación con sobreprecio y aportes ficticios",
    object_value: { eventos_investigados: 12, monto_total_pen: 2_400_000, periodo: "2015-2016" },
    source_url: "https://elcomercio.pe/politica/caso-cocteles-fuerza-popular-cronologia/",
    source_extract: "Los 'cócteles' de Fuerza Popular recaudaron montos muy superiores a los declarados. La fiscalía determinó que parte de los aportes registrados como individuales en realidad provinieron de fuentes corporativas no declaradas.",
    confidence: 0.79, agent_callsign: "el-periodista", verified_by_jueza: false,
    created_at: "2026-05-17T10:20:05Z",
  },
  {
    id: "clm-k7", investigation_id: INV_ID, entity_id: "ent-yoshiyama",
    predicate: "Yoshiyama canalizó fondos de Odebrecht hacia campaña",
    object_value: { rol: "secretario general de campaña 2011", confesion: "colaboración eficaz parcial" },
    source_url: "https://larepublica.pe/politica/yoshiyama-odebrecht-colaboracion/",
    source_extract: "Jaime Yoshiyama fue condenado como intermediario principal en la recepción del millón de dólares que Odebrecht entregó para la campaña presidencial de 2011 de Keiko Fujimori.",
    confidence: 0.90, agent_callsign: "el-detective", verified_by_jueza: true,
    created_at: "2026-05-17T10:24:18Z",
  },
  {
    id: "clm-k8", investigation_id: INV_ID, entity_id: "ent-onpe-2016",
    predicate: "Declaración de aportes 2016 con inconsistencias",
    object_value: { aportantes_cuestionados: 28, monto_cuestionado_pen: 4_800_000 },
    source_url: "https://www.web.onpe.gob.pe/modFinanciamientoPP/consulta/2016",
    source_extract: "En la declaración de financiamiento 2016, al menos 28 aportantes individuales presentaban inconsistencias: direcciones inexistentes, ingresos declarados insuficientes para los montos aportados, o duplicidad con aportantes de 2011.",
    confidence: 0.76, agent_callsign: "la-tasadora", verified_by_jueza: false,
    created_at: "2026-05-17T10:28:40Z",
  },
]

const now = "2026-05-17T10:"
const EVENTS: InvestigationEvent[] = [
  { id: 1, investigation_id: INV_ID, type: "investigation_started", agent_callsign: null, payload: { country: "pe", entity_id: TARGET_ID, investigation_id: INV_ID, locale: "es-PE" }, created_at: `${now}00:00Z` },
  { id: 2, investigation_id: INV_ID, type: "plan_generated", agent_callsign: "sabueso", payload: { plan: PLAN }, created_at: `${now}00:45Z` },

  { id: 3, investigation_id: INV_ID, type: "agent_started", agent_callsign: "el-buscador", payload: { agent: "el-buscador", task: PLAN[0].task }, created_at: `${now}01:00Z` },
  { id: 4, investigation_id: INV_ID, type: "tool_call", agent_callsign: "el-buscador", payload: { agent: "el-buscador", tool: "search_jne", args: { q: "Keiko Fujimori Higuchi" }, cache_hit: false, duration_ms: 1240 }, created_at: `${now}01:12Z` },
  { id: 5, investigation_id: INV_ID, type: "claim_created", agent_callsign: "el-buscador", payload: { claim_id: "clm-k1", entity_id: TARGET_ID, predicate: "Candidata presidencial registrada en JNE", object_value: CLAIMS[0].object_value, source_url: CLAIMS[0].source_url, confidence: 0.99, agent: "el-buscador" as InvestigatorCallsign }, created_at: `${now}01:20Z` },
  { id: 6, investigation_id: INV_ID, type: "agent_finished", agent_callsign: "el-buscador", payload: { agent: "el-buscador", claims_created: 1, cost_usd: 0.03, duration_ms: 20000 }, created_at: `${now}01:30Z` },

  { id: 7, investigation_id: INV_ID, type: "agent_started", agent_callsign: "el-contador", payload: { agent: "el-contador", task: PLAN[1].task }, created_at: `${now}02:00Z` },
  { id: 8, investigation_id: INV_ID, type: "tool_call", agent_callsign: "el-contador", payload: { agent: "el-contador", tool: "search_onpe", args: { partido: "Fuerza Popular", año: 2011 }, cache_hit: false, duration_ms: 2100 }, created_at: `${now}02:30Z` },
  { id: 9, investigation_id: INV_ID, type: "tool_call", agent_callsign: "el-contador", payload: { agent: "el-contador", tool: "search_onpe", args: { partido: "Fuerza Popular", año: 2016 }, cache_hit: false, duration_ms: 1800 }, created_at: `${now}03:00Z` },

  { id: 10, investigation_id: INV_ID, type: "agent_started", agent_callsign: "el-detective", payload: { agent: "el-detective", task: PLAN[2].task }, created_at: `${now}03:30Z` },
  { id: 11, investigation_id: INV_ID, type: "tool_call", agent_callsign: "el-detective", payload: { agent: "el-detective", tool: "search_sunarp", args: { q: "Dionisio Romero Paoletti" }, cache_hit: false, duration_ms: 1560 }, created_at: `${now}04:00Z` },

  { id: 12, investigation_id: INV_ID, type: "claim_created", agent_callsign: "el-contador", payload: { claim_id: "clm-k2", entity_id: "ent-odebrecht", predicate: "Aporte de Odebrecht no declarado ante ONPE", object_value: CLAIMS[1].object_value, source_url: CLAIMS[1].source_url, confidence: 0.91, agent: "el-contador" as InvestigatorCallsign }, created_at: `${now}04:35Z` },

  { id: 13, investigation_id: INV_ID, type: "claim_created", agent_callsign: "el-detective", payload: { claim_id: "clm-k3", entity_id: "ent-romero", predicate: "Aporte encubierto de Dionisio Romero", object_value: CLAIMS[2].object_value, source_url: CLAIMS[2].source_url, confidence: 0.88, agent: "el-detective" as InvestigatorCallsign }, created_at: `${now}08:12Z` },
  { id: 14, investigation_id: INV_ID, type: "edge_discovered", agent_callsign: "el-detective", payload: { edge_id: "edg-k6", from_entity: "ent-romero", to_entity: "ent-fp", edge_type: "aporte-encubierto", weight: 1.5, confidence: 0.85 }, created_at: `${now}08:30Z` },
  { id: 15, investigation_id: INV_ID, type: "edge_discovered", agent_callsign: "el-detective", payload: { edge_id: "edg-k11", from_entity: "ent-romero", to_entity: "ent-yoshiyama", edge_type: "intermedió-entrega", weight: 1.2, confidence: 0.79 }, created_at: `${now}08:45Z` },

  { id: 16, investigation_id: INV_ID, type: "agent_started", agent_callsign: "la-tasadora", payload: { agent: "la-tasadora", task: PLAN[3].task }, created_at: `${now}09:00Z` },
  { id: 17, investigation_id: INV_ID, type: "tool_call", agent_callsign: "la-tasadora", payload: { agent: "la-tasadora", tool: "cross_onpe_sbs", args: { partido: "Fuerza Popular", periodos: ["2011", "2016"] }, cache_hit: false, duration_ms: 3200 }, created_at: `${now}10:00Z` },
  { id: 18, investigation_id: INV_ID, type: "claim_created", agent_callsign: "la-tasadora", payload: { claim_id: "clm-k4", entity_id: "ent-onpe-2011", predicate: "Declaración de aportes 2011 incompleta", object_value: CLAIMS[3].object_value, source_url: CLAIMS[3].source_url, confidence: 0.84, agent: "la-tasadora" as InvestigatorCallsign }, created_at: `${now}12:45Z` },

  { id: 19, investigation_id: INV_ID, type: "agent_finished", agent_callsign: "el-contador", payload: { agent: "el-contador", claims_created: 1, cost_usd: 0.08, duration_ms: 120000 }, created_at: `${now}13:00Z` },
  { id: 20, investigation_id: INV_ID, type: "agent_finished", agent_callsign: "el-detective", payload: { agent: "el-detective", claims_created: 2, cost_usd: 0.12, duration_ms: 150000 }, created_at: `${now}13:15Z` },

  { id: 21, investigation_id: INV_ID, type: "agent_started", agent_callsign: "el-letrado", payload: { agent: "el-letrado", task: PLAN[4].task }, created_at: `${now}14:00Z` },
  { id: 22, investigation_id: INV_ID, type: "tool_call", agent_callsign: "el-letrado", payload: { agent: "el-letrado", tool: "search_pj_cej", args: { nombre: "Keiko Sofia Fujimori Higuchi", delito: "lavado de activos" }, cache_hit: false, duration_ms: 2800 }, created_at: `${now}14:30Z` },
  { id: 23, investigation_id: INV_ID, type: "claim_created", agent_callsign: "el-letrado", payload: { claim_id: "clm-k5", entity_id: "ent-exp-judicial", predicate: "Proceso penal por lavado de activos", object_value: CLAIMS[4].object_value, source_url: CLAIMS[4].source_url, confidence: 0.93, agent: "el-letrado" as InvestigatorCallsign }, created_at: `${now}16:30Z` },
  { id: 24, investigation_id: INV_ID, type: "agent_finished", agent_callsign: "el-letrado", payload: { agent: "el-letrado", claims_created: 1, cost_usd: 0.09, duration_ms: 180000 }, created_at: `${now}17:00Z` },

  { id: 25, investigation_id: INV_ID, type: "agent_started", agent_callsign: "el-periodista", payload: { agent: "el-periodista", task: PLAN[5].task }, created_at: `${now}17:30Z` },
  { id: 26, investigation_id: INV_ID, type: "tool_call", agent_callsign: "el-periodista", payload: { agent: "el-periodista", tool: "search_news", args: { q: "Keiko Fujimori caso cócteles lavado", fuentes: ["elcomercio.pe", "idl-reporteros.pe", "ojo-publico.com"] }, cache_hit: true, duration_ms: 980 }, created_at: `${now}18:00Z` },
  { id: 27, investigation_id: INV_ID, type: "claim_created", agent_callsign: "el-periodista", payload: { claim_id: "clm-k6", entity_id: "ent-cocktail", predicate: "Cócteles de recaudación con sobreprecio y aportes ficticios", object_value: CLAIMS[5].object_value, source_url: CLAIMS[5].source_url, confidence: 0.79, agent: "el-periodista" as InvestigatorCallsign }, created_at: `${now}20:05Z` },
  { id: 28, investigation_id: INV_ID, type: "claim_created", agent_callsign: "el-detective", payload: { claim_id: "clm-k7", entity_id: "ent-yoshiyama", predicate: "Yoshiyama canalizó fondos de Odebrecht hacia campaña", object_value: CLAIMS[6].object_value, source_url: CLAIMS[6].source_url, confidence: 0.90, agent: "el-detective" as InvestigatorCallsign }, created_at: `${now}24:18Z` },
  { id: 29, investigation_id: INV_ID, type: "agent_finished", agent_callsign: "el-periodista", payload: { agent: "el-periodista", claims_created: 1, cost_usd: 0.05, duration_ms: 90000 }, created_at: `${now}25:00Z` },
  { id: 30, investigation_id: INV_ID, type: "agent_finished", agent_callsign: "la-tasadora", payload: { agent: "la-tasadora", claims_created: 2, cost_usd: 0.11, duration_ms: 200000 }, created_at: `${now}25:30Z` },

  { id: 31, investigation_id: INV_ID, type: "claim_created", agent_callsign: "la-tasadora", payload: { claim_id: "clm-k8", entity_id: "ent-onpe-2016", predicate: "Declaración de aportes 2016 con inconsistencias", object_value: CLAIMS[7].object_value, source_url: CLAIMS[7].source_url, confidence: 0.76, agent: "la-tasadora" as InvestigatorCallsign }, created_at: `${now}28:40Z` },

  { id: 32, investigation_id: INV_ID, type: "agent_started", agent_callsign: "la-jueza", payload: { agent: "la-jueza", task: PLAN[6].task }, created_at: `${now}29:00Z` },
  { id: 33, investigation_id: INV_ID, type: "agent_finished", agent_callsign: "la-jueza", payload: { agent: "la-jueza", claims_created: 0, cost_usd: 0.15, duration_ms: 60000 }, created_at: `${now}30:00Z` },

  { id: 34, investigation_id: INV_ID, type: "synthesis_started", agent_callsign: "sabueso", payload: { claim_count: 8 }, created_at: `${now}30:30Z` },
  { id: 35, investigation_id: INV_ID, type: "investigation_complete", agent_callsign: null, payload: { dossier_url: `/i/${INV_ID}/dossier`, total_claims: 8, total_cost_usd: 0.63, duration_ms: 1830000 }, created_at: `${now}31:00Z` },
]

const DOSSIER_MD = `# Dossier — Keiko Fujimori Higuchi

> **Caso Cócteles — Aportes no declarados a campañas**
> Estado: **investigación completa** · Costo total: $0.63 USD · Duración: ~30 min

---

## Resumen ejecutivo

Sabueso identificó **tres zonas críticas de fricción** entre lo declarado por Keiko Fujimori y su partido Fuerza Popular ante los organismos electorales (JNE/ONPE) y los registros cruzados por el equipo investigador:

1. **Financiamiento extranjero no declarado** — US$ 1 millón de Odebrecht canalizado vía Jaime Yoshiyama para la campaña 2011.
2. **Aportes individuales encubiertos (pitufeo)** — US$ 3.65 millones de Dionisio Romero Paoletti fraccionados entre decenas de falsos aportantes.
3. **Discrepancia masiva en declaraciones ONPE** — diferencia de S/. 13.2M entre lo declarado y los flujos reales estimados para la campaña 2011.

---

## Hallazgos verificados (confianza ≥ 0.85)

### 1. Registro electoral y hoja de vida
**Keiko Sofia Fujimori Higuchi** (DNI 25209800) fue candidata presidencial en 2011, 2016 y 2021 por Fuerza Popular. Su hoja de vida JNE está disponible en los registros públicos del Jurado Nacional de Elecciones.
<conf v="0.99" /><src url="https://plataformaelectoral.jne.gob.pe/Candidato/HojaVida/25209800" type="jne" />

### 2. Aporte de Odebrecht no declarado
Marcelo Odebrecht declaró ante la fiscalía brasileña haber entregado **US$ 1 millón** a la campaña presidencial 2011 de Keiko Fujimori a través de su entonces secretario general de campaña, Jaime Yoshiyama. Este aporte no figura en ninguna declaración ante ONPE.
<conf v="0.91" /><src url="https://www.idl-reporteros.pe/odebrecht-keiko-fujimori/" type="news" />

### 3. Aporte encubierto de Dionisio Romero Paoletti
Romero Paoletti admitió en juicio oral haber entregado **US$ 3.65 millones** a la campaña de 2011. Los fondos fueron fraccionados entre 32 personas (pitufeo) para evadir los límites legales de aportes individuales.
<conf v="0.88" /><src url="https://ojo-publico.com/caso-cocteles-romero-paoletti/" type="news" />

### 4. Yoshiyama como intermediario clave
Jaime Yoshiyama fue condenado como intermediario principal en la recepción del millón de dólares de Odebrecht. Su rol como coordinador de campaña le dio acceso directo al manejo financiero del partido.
<conf v="0.90" /><src url="https://larepublica.pe/politica/yoshiyama-odebrecht-colaboracion/" type="news" />

### 5. Proceso penal activo por lavado de activos
El Expediente **00299-2017** ante la Corte Suprema de Justicia acusa a Keiko Fujimori como presunta líder de una organización criminal al interior de Fuerza Popular dedicada al lavado de activos para financiar campañas.
<conf v="0.93" /><src url="https://cej.pj.gob.pe/cej/forms/detalleform.html?00299-2017" type="legalize" />

---

## Hallazgos en evaluación (confianza 0.60 – 0.84)

### 6. Declaración ONPE 2011 con discrepancia masiva
Fuerza Popular declaró **S/. 1.2M** en aportes ante ONPE para la campaña 2011. Las investigaciones fiscales estiman flujos reales superiores a **S/. 14M** — una diferencia de **S/. 13.2 millones** sin sustento documental.
<conf v="0.84" /><src url="https://www.web.onpe.gob.pe/modFinanciamientoPP/consulta/2011" type="other" />

### 7. Cócteles de recaudación con aportes ficticios
Se investigaron 12 eventos de recaudación ("cócteles") organizados por Fuerza Popular entre 2015-2016 con un monto total declarado de S/. 2.4M. La fiscalía determinó que parte de los aportes registrados como individuales provinieron de fuentes corporativas no declaradas.
<conf v="0.79" /><src url="https://elcomercio.pe/politica/caso-cocteles-fuerza-popular-cronologia/" type="news" />

### 8. Declaración ONPE 2016 con inconsistencias
En la rendición de cuentas 2016, al menos **28 aportantes individuales** presentaban inconsistencias: direcciones inexistentes, ingresos insuficientes para los montos declarados, o duplicidad con aportantes de campañas anteriores.
<conf v="0.76" /><src url="https://www.web.onpe.gob.pe/modFinanciamientoPP/consulta/2016" type="other" />

---

## Red de vínculos principales

\`\`\`
Keiko Fujimori ──lidera──▶ Fuerza Popular
       │                        ▲
       │                        │ aporte no declarado (US$ 1.2M)
       ├─coordinador─▶ Yoshiyama ◀─recibió─ Odebrecht
       │                        ▲
       │                        │ intermedió (US$ 3.65M)
       │                   Romero Paoletti
       │
       └─investigada─▶ Exp. 00299-2017 (lavado de activos)
\`\`\`

---

## Fuentes consultadas

| Fuente | Tipo | Claims derivados |
|--------|------|-----------------|
| JNE · Plataforma Electoral | Registro público | 1 |
| ONPE · Financiamiento PP | Registro público | 2 |
| IDL-Reporteros | Periodismo investigativo | 1 |
| Ojo Público | Periodismo investigativo | 1 |
| El Comercio | Prensa | 1 |
| La República | Prensa | 1 |
| Poder Judicial · CEJ | Registro judicial | 1 |

---

## Metodología y limitaciones

- **7 investigadores** ejecutaron tareas en paralelo durante ~30 minutos.
- **Costo total LLM:** US$ 0.63 (dentro del presupuesto objetivo de $0.65).
- Las fuentes primarias (JNE, ONPE, PJ-CEJ) fueron consultadas directamente. Las fuentes periodísticas fueron corroboradas cruzando al menos dos medios independientes.
- La investigación se limita a registros públicos disponibles en línea. No incluye documentos clasificados, testimonios reservados, ni acceso a cuentas bancarias privadas.

---

*Generado por Sabueso · ${new Date().toISOString().slice(0, 10)}*
`

const ACTIVE_DELEGATIONS: ActiveDelegation[] = [
  { id: "del-k1", from: "sabueso", to: "el-buscador", status: "done", task: "Localizar DNI + JNE" },
  { id: "del-k2", from: "sabueso", to: "el-contador", status: "done", task: "Auditar ONPE" },
  { id: "del-k3", from: "sabueso", to: "el-detective", status: "done", task: "Mapear red" },
  { id: "del-k4", from: "sabueso", to: "la-tasadora", status: "done", task: "Cruzar flujos" },
  { id: "del-k5", from: "sabueso", to: "el-letrado", status: "done", task: "Revisar causas penales" },
  { id: "del-k6", from: "sabueso", to: "el-periodista", status: "done", task: "Cobertura prensa" },
  { id: "del-k7", from: "sabueso", to: "la-jueza", status: "done", task: "Verificar claims" },
]

export const KEIKO_MOCK_STATE: ComposedInvestigationState = {
  id: INV_ID,
  target_name: TARGET_NAME,
  status: "complete",
  progress: 100,
  plan: PLAN,
  agents: AGENTS,
  entities: ENTITIES,
  edges: EDGES,
  claims: CLAIMS,
  dossier_md: DOSSIER_MD,
  activeDelegations: ACTIVE_DELEGATIONS,
  events: EVENTS,
}
