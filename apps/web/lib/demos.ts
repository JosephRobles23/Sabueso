/**
 * Demo targets — fuente de verdad para los 5 funcionarios cacheados que se
 * reproducen en `mode=replay`. La justificación editorial vive en
 * `docs/demo-targets.md`; este archivo es lo que consume el frontend.
 *
 * El campo `investigation_id` se llena DESPUÉS de correr
 * `pnpm tsx scripts/record-demos.ts` con la infra en vivo. Mientras esté
 * vacío, el demo aparece en la lista como "pendiente de cachear".
 */
import type { Country } from "@sabueso/shared-types";

export interface DemoTarget {
  /** kebab-case stable id. Usado en URLs de video y como key React. */
  slug: string;
  /** Nombre del funcionario / entidad mostrado en la UI. */
  name: string;
  /** Categoría según C4 §12.1 — usada para badge / agrupación. */
  category:
    | "candidato-presidencial"
    | "congresista"
    | "ex-presidente"
    | "gobernador-regional"
    | "tecnico-mef-minsa";
  /** Etiqueta breve para chips en el toggle. */
  categoryLabel: string;
  /** Caso central que el dossier ataca (1 línea, para descripción en el toggle). */
  caseLine: string;
  /** País — todos los demos cacheados son Perú. */
  country: Country;
  /**
   * UUID de la `investigations` row en Supabase cacheada en pre-cache. Vacío
   * mientras no se haya corrido el pre-cache; el toggle muestra estos como
   * "pendiente" y los oculta del replay activo.
   */
  investigation_id: string;
  /**
   * Ruta del video screen-recording 60s. Vacío hasta que se grabe.
   * Puede ser ruta local (`/demos/<slug>.webm`) o Vercel Blob URL.
   */
  video_url: string;
}

export const DEMO_TARGETS: DemoTarget[] = [
  {
    slug: "keiko-fujimori",
    name: "Keiko Fujimori Higuchi",
    category: "candidato-presidencial",
    categoryLabel: "Candidato 2026",
    caseLine: "Caso Cócteles — aportes no declarados a campañas",
    country: "pe",
    investigation_id: "demo-keiko-fujimori",
    video_url: "",
  },
  {
    slug: "edgar-tello",
    name: "Edgar Tello Montes",
    category: "congresista",
    categoryLabel: "Congresista",
    caseLine: "Mochasueldos — descuentos no autorizados a personal",
    country: "pe",
    investigation_id: "",
    video_url: "",
  },
  {
    slug: "alejandro-toledo",
    name: "Alejandro Toledo Manrique",
    category: "ex-presidente",
    categoryLabel: "Ex-presidente",
    caseLine: "Caso Odebrecht — sentencia firme 2024",
    country: "pe",
    investigation_id: "",
    video_url: "",
  },
  {
    slug: "wilfredo-oscorima",
    name: "Wilfredo Oscorima Núñez",
    category: "gobernador-regional",
    categoryLabel: "Gobernador",
    caseLine: "Caso Rolex + denuncias Contraloría",
    country: "pe",
    investigation_id: "",
    video_url: "",
  },
  {
    slug: "minsa",
    name: "Ministerio de Salud del Perú",
    category: "tecnico-mef-minsa",
    categoryLabel: "MINSA · técnico",
    caseLine: "Patrones SEACE 2014-2024",
    country: "pe",
    investigation_id: "",
    video_url: "",
  },
];

/** Búsqueda por slug — usada por el toggle al construir el href de replay. */
export function findDemoBySlug(slug: string): DemoTarget | null {
  return DEMO_TARGETS.find((d) => d.slug === slug) ?? null;
}

/** Lookup inverso — útil para el shell que recibe la url ?mode=replay&id=<uuid>. */
export function findDemoByInvestigationId(id: string): DemoTarget | null {
  return DEMO_TARGETS.find((d) => d.investigation_id === id) ?? null;
}

/** Sólo los que ya fueron cacheados (tienen investigation_id). */
export function listReadyDemos(): DemoTarget[] {
  return DEMO_TARGETS.filter((d) => d.investigation_id.length > 0);
}
