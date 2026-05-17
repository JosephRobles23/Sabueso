import type { Metadata, Viewport } from "next";
import { getMessages, getLocale, getTimeZone } from "next-intl/server";

import { Providers } from "./providers";
import { fontVariables } from "./fonts";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Sabueso · Tras la pista de la corrupción",
    template: "%s · Sabueso",
  },
  description:
    "Una redacción de IA que audita funcionarios públicos en LATAM cruzando registros oficiales en vivo.",
  applicationName: "Sabueso",
  authors: [{ name: "Sabueso · hack@latam 2026" }],
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"),
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#faf9f5" },
    { media: "(prefers-color-scheme: dark)", color: "#141413" },
  ],
  width: "device-width",
  initialScale: 1,
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const [locale, messages, timeZone] = await Promise.all([
    getLocale(),
    getMessages(),
    getTimeZone(),
  ]);

  return (
    <html lang={locale} suppressHydrationWarning className={fontVariables}>
      <body className="min-h-dvh bg-[var(--color-canvas)] text-[var(--color-text-primary)]">
        <Providers locale={locale} messages={messages} timeZone={timeZone}>
          {children}
        </Providers>
      </body>
    </html>
  );
}
