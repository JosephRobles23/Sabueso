/**
 * Persistencia del modo replay/live para el demo del pitch.
 *
 * El frontend persiste la elección en cookie `sabueso:demo-mode` para que
 * sobreviva refresh y reloads server-side. Default: "replay" — más seguro
 * para la primera apertura del jurado (sin costos LLM accidentales).
 */

export type DemoMode = "replay" | "live";
export const DEMO_MODE_COOKIE = "sabueso:demo-mode";
export const DEFAULT_DEMO_MODE: DemoMode = "replay";

export function normalizeDemoMode(value: string | undefined): DemoMode {
  return value === "live" || value === "replay" ? value : DEFAULT_DEMO_MODE;
}
