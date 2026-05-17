import { cookies, headers } from "next/headers";
import { getRequestConfig } from "next-intl/server";

export const locales = ["es", "en"] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale: Locale = "es";

const COOKIE_NAME = "sabueso-locale";

function pickLocale(candidate: string | undefined | null): Locale {
  if (!candidate) return defaultLocale;
  const head = candidate.split(",")[0]?.toLowerCase().slice(0, 2);
  return locales.includes(head as Locale) ? (head as Locale) : defaultLocale;
}

export async function resolveLocale(): Promise<Locale> {
  const cookieStore = await cookies();
  const fromCookie = cookieStore.get(COOKIE_NAME)?.value;
  if (fromCookie && locales.includes(fromCookie as Locale)) {
    return fromCookie as Locale;
  }
  const headerStore = await headers();
  return pickLocale(headerStore.get("accept-language"));
}

export default getRequestConfig(async () => {
  const locale = await resolveLocale();
  return {
    locale,
    messages: (await import(`./messages/${locale}.json`)).default,
    timeZone: "America/Lima",
  };
});
