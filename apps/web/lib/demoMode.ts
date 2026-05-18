/**
 * Persistencia del modo replay/live para el demo del pitch.
 *
 * El frontend persiste la elección en cookie `sabueso:demo-mode` para que
 * sobreviva refresh y reloads server-side. Default: "replay" — más seguro
 * para la primera apertura del jurado (sin costos LLM accidentales).
 */
import { cookies } from "next/headers";

export type DemoMode = "replay" | "live";
export const DEMO_MODE_COOKIE = "sabueso:demo-mode";
export const DEFAULT_DEMO_MODE: DemoMode = "replay";

function normalize(value: string | undefined): DemoMode {
  return value === "live" || value === "replay" ? value : DEFAULT_DEMO_MODE;
}

/** Server-side: lee la cookie en RSC. */
export async function getDemoMode(): Promise<DemoMode> {
  const store = await cookies();
  return normalize(store.get(DEMO_MODE_COOKIE)?.value);
}
