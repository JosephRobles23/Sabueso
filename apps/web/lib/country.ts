/**
 * Persistencia + helpers del país activo (S-18).
 *
 * - Cookie `sabueso:country` guarda la elección entre cargas.
 * - URL `?c=<code>` la sobrescribe (útil para deep-linking de demos).
 * - Default: "pe" (Perú es first-class; el resto opera en preview mode).
 */
import type { Country } from "@sabueso/shared-types";

export const COUNTRY_COOKIE = "sabueso:country";
export const DEFAULT_COUNTRY: Country = "pe";

export const COUNTRIES: ReadonlyArray<{
  code: Country;
  name: string;
  /** Bandera renderizada como emoji (preferido por el task) — fallback safe en monospace. */
  flag: string;
  /** True si el país tiene tools completas. Para preview mode el resto. */
  firstClass: boolean;
}> = [
  { code: "pe", name: "Perú", flag: "🇵🇪", firstClass: true },
  { code: "cl", name: "Chile", flag: "🇨🇱", firstClass: false },
  { code: "mx", name: "México", flag: "🇲🇽", firstClass: false },
  { code: "sv", name: "El Salvador", flag: "🇸🇻", firstClass: false },
];

export function normalizeCountry(value: string | undefined | null): Country {
  if (value === "pe" || value === "cl" || value === "mx" || value === "sv") return value;
  return DEFAULT_COUNTRY;
}

/** Server-side: lee la cookie en RSC. */
export async function getCountry(): Promise<Country> {
  const { cookies } = await import("next/headers");
  const store = await cookies();
  return normalizeCountry(store.get(COUNTRY_COOKIE)?.value);
}

/** Client-side: lee cookie del document. Devuelve null en SSR. */
export function readCountryCookie(): Country | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|;\\s*)${COUNTRY_COOKIE}=([^;]+)`));
  if (!match) return null;
  return normalizeCountry(decodeURIComponent(match[1]!));
}

/** Client-side: escribe la cookie y opcionalmente refleja en URL. */
export function writeCountryCookie(country: Country): void {
  if (typeof document === "undefined") return;
  const oneMonth = 60 * 60 * 24 * 30;
  document.cookie = `${COUNTRY_COOKIE}=${country}; path=/; max-age=${oneMonth}; SameSite=Lax`;
}
