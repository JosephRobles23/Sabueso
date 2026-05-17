"use server";

import { cookies } from "next/headers";
import { revalidatePath } from "next/cache";

import { locales, type Locale } from "@/i18n";

const COOKIE_NAME = "sabueso-locale";

export async function setLocale(locale: Locale) {
  if (!locales.includes(locale)) return;
  const cookieStore = await cookies();
  cookieStore.set(COOKIE_NAME, locale, {
    path: "/",
    maxAge: 60 * 60 * 24 * 365,
    sameSite: "lax",
  });
  revalidatePath("/", "layout");
}
