/**
 * mockInvestigationState — fixture for /dev/cinema and the composite gallery.
 *
 * Defines the *composed* state shape that S-12 composites consume. Strictly a
 * superset of the live `InvestigationState` (from useInvestigation): the extra
 * fields (plan, entities, edges, claims, dossier_md, activeDelegations) are
 * what S-10's hook will emit once it lands. Until then, the shell derives
 * them from the live event stream via `deriveComposedState`.
 */

import type {
  AgentStatus,
  Claim,
  Entity,
  Edge,
  InvestigationEvent,
  InvestigationStatus,
  InvestigatorCallsign,
  PlanStep,
} from "@sabueso/shared-types";

/** Semantic class drives node/edge color in the InvestigationGraph. */
export type GraphSemantic =
  | "declared"
  | "discovered"
  | "ambiguous"
  | "suspicious"
  | "conflict"
  | "verified";

export interface GraphEntity {
  id: string;
  name: string;
  type: Entity["type"];
  semantic: GraphSemantic;
  /** Optional pre-computed layout position. If absent, the graph runs its own simulation. */
  x?: number;
  y?: number;
}

export interface GraphEdge {
  id: string;
  from: string;
  to: string;
  type: string;
  /** [0, 1] — drives stroke width. */
  confidence: number;
  /** Bigger = more visual weight (e.g. amount in soles). */
  weight: number;
  semantic: GraphSemantic;
  /** ISO date for time-scrubbing. */
  occurred_at?: string;
}

export interface ActiveDelegation {
  id: string;
  from: InvestigatorCallsign;
  to: InvestigatorCallsign;
  status: "running" | "done" | "blocked";
  task: string;
}

export interface AgentSnapshot {
  callsign: InvestigatorCallsign;
  status: AgentStatus;
  detail?: string;
  /** Currently-assigned lead, if any. */
  currentLead?: string;
}

/** State the composites consume. Strict superset of useInvestigation's state. */
export interface ComposedInvestigationState {
  id: string;
  target_name: string;
  status: InvestigationStatus;
  progress: number;
  plan: PlanStep[];
  agents: Record<string, AgentSnapshot>;
  entities: GraphEntity[];
  edges: GraphEdge[];
  claims: Claim[];
  dossier_md: string;
  activeDelegations: ActiveDelegation[];
  events: InvestigationEvent[];
}

// ─────────────────────────────────────────────────────────────────────────────
// Fixture
// ─────────────────────────────────────────────────────────────────────────────

const TARGET_NAME = "Vladimir Cerrón Rojas";
const TARGET_ENTITY_ID = "ent-target";

const PLAN: PlanStep[] = [
  { agent: "el-buscador", task: "Localizar RUC, DNI y declaraciones juradas en JNE", priority: 1 },
  { agent: "la-tasadora", task: "Cruzar declaraciones SUNARP con bienes inmuebles", priority: 2 },
  { agent: "el-contador", task: "Auditar contratos SEACE 2014-2024", priority: 2 },
  { agent: "el-letrado", task: "Revisar causas penales y sanciones administrativas", priority: 3 },
  { agent: "el-detective", task: "Mapear red de parientes y socios", priority: 3 },
  { agent: "el-periodista", task: "Recoger menciones en prensa de los últimos 5 años", priority: 4 },
  { agent: "la-jueza", task: "Verificar claims con score ≥ 0.6 vía Mixture-of-Agents", priority: 5 },
];

const AGENTS: ComposedInvestigationState["agents"] = {
  sabueso: { callsign: "sabueso", status: "thinking", detail: "Coordinando plan" },
  "el-buscador": {
    callsign: "el-buscador",
    status: "done",
    detail: "RUC 20100070970",
    currentLead: "DNI ubicado",
  },
  "la-tasadora": {
    callsign: "la-tasadora",
    status: "working",
    detail: "Querying SUNARP-Lima",
    currentLead: "3 inmuebles en Huancayo",
  },
  "el-contador": {
    callsign: "el-contador",
    status: "working",
    detail: "4 contratos · S/. 10.2M",
    currentLead: "Contratos sin licitación",
  },
  "el-letrado": { callsign: "el-letrado", status: "idle" },
  "el-detective": {
    callsign: "el-detective",
    status: "blocked",
    detail: "403 en SUNARP-board",
  },
  "el-periodista": { callsign: "el-periodista", status: "idle" },
  "la-jueza": { callsign: "la-jueza", status: "thinking", detail: "3 claims en cola" },
};

const ENTITIES: GraphEntity[] = [
  { id: TARGET_ENTITY_ID, name: TARGET_NAME, type: "person", semantic: "verified" },
  { id: "ent-mvc", name: "Movimiento Político MVC", type: "company", semantic: "declared" },
  {
    id: "ent-constructora",
    name: "Constructora Hermanos R. S.A.C.",
    type: "company",
    semantic: "suspicious",
  },
  {
    id: "ent-municipalidad",
    name: "Municipalidad Provincial de Junín",
    type: "government_entity",
    semantic: "declared",
  },
  {
    id: "ent-contrato-2017",
    name: "Contrato SEACE-2017-04823",
    type: "contract",
    semantic: "ambiguous",
  },
  {
    id: "ent-hermano",
    name: "Waldemar Cerrón Rojas",
    type: "person",
    semantic: "discovered",
  },
  {
    id: "ent-inmueble",
    name: "Inmueble Av. Giráldez 1200, Huancayo",
    type: "company",
    semantic: "conflict",
  },
];

const EDGES: GraphEdge[] = [
  {
    id: "edg-1",
    from: TARGET_ENTITY_ID,
    to: "ent-mvc",
    type: "lidera",
    confidence: 0.98,
    weight: 1,
    semantic: "declared",
    occurred_at: "2012-06-01",
  },
  {
    id: "edg-2",
    from: TARGET_ENTITY_ID,
    to: "ent-hermano",
    type: "es-hermano-de",
    confidence: 0.95,
    weight: 1,
    semantic: "verified",
    occurred_at: "2014-01-15",
  },
  {
    id: "edg-3",
    from: "ent-hermano",
    to: "ent-constructora",
    type: "es-accionista",
    confidence: 0.78,
    weight: 0.6,
    semantic: "discovered",
    occurred_at: "2016-03-22",
  },
  {
    id: "edg-4",
    from: "ent-constructora",
    to: "ent-contrato-2017",
    type: "adjudicataria",
    confidence: 0.92,
    weight: 1.5,
    semantic: "suspicious",
    occurred_at: "2017-09-04",
  },
  {
    id: "edg-5",
    from: "ent-municipalidad",
    to: "ent-contrato-2017",
    type: "convocante",
    confidence: 0.98,
    weight: 1,
    semantic: "declared",
    occurred_at: "2017-07-12",
  },
  {
    id: "edg-6",
    from: TARGET_ENTITY_ID,
    to: "ent-inmueble",
    type: "propietario-no-declarado",
    confidence: 0.54,
    weight: 0.8,
    semantic: "conflict",
    occurred_at: "2019-11-30",
  },
];

const CLAIMS: Claim[] = [
  {
    id: "clm-1",
    investigation_id: "inv-cinema",
    entity_id: TARGET_ENTITY_ID,
    predicate: "RUC asociado",
    object_value: { ruc: "20100070970" },
    source_url: "https://plataformaelectoral.jne.gob.pe/Candidato/Declaracion/12345",
    source_extract: "RUC declarado en hoja de vida JNE.",
    confidence: 0.97,
    agent_callsign: "el-buscador",
    verified_by_jueza: true,
    created_at: "2026-05-15T14:02:11Z",
  },
  {
    id: "clm-2",
    investigation_id: "inv-cinema",
    entity_id: "ent-contrato-2017",
    predicate: "monto adjudicado",
    object_value: { amount_pen: 4_820_000, year: 2017 },
    source_url: "https://prodapp2.seace.gob.pe/seacebus-uiwd/consulta/04823",
    source_extract:
      "Adjudicación directa por S/. 4'820,000 a Constructora Hermanos R. S.A.C. sin proceso de licitación pública.",
    confidence: 0.84,
    agent_callsign: "el-contador",
    verified_by_jueza: false,
    created_at: "2026-05-15T14:04:42Z",
  },
  {
    id: "clm-3",
    investigation_id: "inv-cinema",
    entity_id: "ent-inmueble",
    predicate: "propietario probable",
    object_value: { address: "Av. Giráldez 1200, Huancayo" },
    source_url: "https://www.sunarp.gob.pe/registros/predios/junin/01234",
    source_extract:
      "Predio inscrito a nombre de tercero ligado al ámbito familiar — no figura en declaración jurada del funcionario.",
    confidence: 0.56,
    agent_callsign: "la-tasadora",
    verified_by_jueza: false,
    created_at: "2026-05-15T14:07:08Z",
  },
];

const DOSSIER_MD = `# Dossier — ${TARGET_NAME}

> Estado: **investigación en curso** · Última actualización: 14:07 UTC

## Resumen ejecutivo

Sabueso identifica **dos zonas de fricción** entre lo declarado por el
funcionario y los registros públicos cruzados por el equipo.

## Hallazgos verificados

- **RUC 20100070970** confirmado en JNE.<conf v="0.97" /><src url="https://plataformaelectoral.jne.gob.pe/Candidato/Declaracion/12345" type="jne" />
- Vínculo fraterno con **Waldemar Cerrón** corroborado vía RENIEC.<conf v="0.95" />

## Hallazgos en evaluación

- Contrato **SEACE-2017-04823** por S/. 4'820,000 adjudicado a empresa
  vinculada a familiar del funcionario.<conf v="0.84" /><src url="https://prodapp2.seace.gob.pe/seacebus-uiwd/consulta/04823" type="seace" />
- Inmueble en Av. Giráldez 1200 (Huancayo) **no figura en la declaración
  jurada** pero registra titularidad indirecta.<conf v="0.56" /><src url="https://www.sunarp.gob.pe/registros/predios/junin/01234" type="sunarp" />

## Próximos pasos

La Jueza verificará el claim del contrato 04823 contra los registros
notariales antes de elevar la confianza por encima de 0.85.
`;

const ACTIVE_DELEGATIONS: ActiveDelegation[] = [
  {
    id: "del-1",
    from: "sabueso",
    to: "la-tasadora",
    status: "running",
    task: "Cruzar SUNARP",
  },
  {
    id: "del-2",
    from: "sabueso",
    to: "el-contador",
    status: "running",
    task: "Auditar SEACE",
  },
  {
    id: "del-3",
    from: "sabueso",
    to: "el-buscador",
    status: "done",
    task: "Localizar RUC",
  },
  {
    id: "del-4",
    from: "el-contador",
    to: "el-detective",
    status: "blocked",
    task: "Mapear accionariado",
  },
];

const EVENTS: InvestigationEvent[] = [
  {
    id: 1,
    investigation_id: "inv-cinema",
    type: "investigation_started",
    agent_callsign: null,
    payload: { country: "pe", entity_id: TARGET_ENTITY_ID },
    created_at: "2026-05-15T13:55:00Z",
  },
  {
    id: 2,
    investigation_id: "inv-cinema",
    type: "plan_generated",
    agent_callsign: "sabueso",
    payload: { plan: PLAN },
    created_at: "2026-05-15T13:55:42Z",
  },
  {
    id: 3,
    investigation_id: "inv-cinema",
    type: "agent_started",
    agent_callsign: "el-buscador",
    payload: { task: PLAN[0].task },
    created_at: "2026-05-15T13:56:00Z",
  },
  {
    id: 4,
    investigation_id: "inv-cinema",
    type: "tool_call",
    agent_callsign: "el-buscador",
    payload: { tool: "search_jne", args: { q: TARGET_NAME }, cache_hit: false, duration_ms: 812 },
    created_at: "2026-05-15T13:56:14Z",
  },
  {
    id: 5,
    investigation_id: "inv-cinema",
    type: "claim_created",
    agent_callsign: "el-buscador",
    payload: { claim_id: "clm-1", confidence: 0.97, predicate: "RUC asociado" },
    created_at: "2026-05-15T14:02:11Z",
  },
  {
    id: 6,
    investigation_id: "inv-cinema",
    type: "agent_finished",
    agent_callsign: "el-buscador",
    payload: { claims_created: 1, cost_usd: 0.04, duration_ms: 372_111 },
    created_at: "2026-05-15T14:02:30Z",
  },
  {
    id: 7,
    investigation_id: "inv-cinema",
    type: "agent_started",
    agent_callsign: "el-contador",
    payload: { task: PLAN[2].task },
    created_at: "2026-05-15T14:03:00Z",
  },
  {
    id: 8,
    investigation_id: "inv-cinema",
    type: "tool_call",
    agent_callsign: "el-contador",
    payload: { tool: "search_seace", args: { ruc: "20100070970" }, cache_hit: true, duration_ms: 218 },
    created_at: "2026-05-15T14:03:42Z",
  },
  {
    id: 9,
    investigation_id: "inv-cinema",
    type: "claim_created",
    agent_callsign: "el-contador",
    payload: { claim_id: "clm-2", confidence: 0.84, predicate: "monto adjudicado" },
    created_at: "2026-05-15T14:04:42Z",
  },
  {
    id: 10,
    investigation_id: "inv-cinema",
    type: "edge_discovered",
    agent_callsign: "el-detective",
    payload: { edge_id: "edg-3", from_entity: "ent-hermano", to_entity: "ent-constructora" },
    created_at: "2026-05-15T14:05:30Z",
  },
  {
    id: 11,
    investigation_id: "inv-cinema",
    type: "agent_started",
    agent_callsign: "la-tasadora",
    payload: { task: PLAN[1].task },
    created_at: "2026-05-15T14:06:00Z",
  },
  {
    id: 12,
    investigation_id: "inv-cinema",
    type: "claim_created",
    agent_callsign: "la-tasadora",
    payload: { claim_id: "clm-3", confidence: 0.56, predicate: "propietario probable" },
    created_at: "2026-05-15T14:07:08Z",
  },
];

export const MOCK_INVESTIGATION_STATE: ComposedInvestigationState = {
  id: "inv-cinema",
  target_name: TARGET_NAME,
  status: "running",
  progress: 38,
  plan: PLAN,
  agents: AGENTS,
  entities: ENTITIES,
  edges: EDGES,
  claims: CLAIMS,
  dossier_md: DOSSIER_MD,
  activeDelegations: ACTIVE_DELEGATIONS,
  events: EVENTS,
};
