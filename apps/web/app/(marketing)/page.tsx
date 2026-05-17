import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Button } from "@/components/ui/button";
import { INVESTIGATORS } from "@sabueso/shared-types";

export default async function MarketingPage() {
  const t = await getTranslations("marketing");

  return (
    <main className="mx-auto max-w-5xl px-6 py-16 sm:py-24">
      <section className="space-y-6">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-text-muted)]">
          hack@latam 2026 · multi-agent investigative journalism
        </p>
        <h1 className="font-display text-5xl leading-[0.95] tracking-tight sm:text-7xl">
          {t("title")}
          <span className="block text-[var(--color-accent)]">{t("subtitle")}</span>
        </h1>
        <p className="max-w-2xl text-lg text-[var(--color-text-secondary)]">{t("description")}</p>
        <div className="flex flex-wrap gap-3">
          <Button asChild size="lg">
            <Link href="/app">{t("ctaPrimary")}</Link>
          </Button>
          <Button asChild size="lg" variant="outline">
            <Link href="#features">{t("ctaSecondary")}</Link>
          </Button>
        </div>
      </section>

      <section id="features" className="mt-24 space-y-8">
        <h2 className="font-display text-3xl tracking-tight">{t("featuresTitle")}</h2>
        <ul className="grid gap-4 sm:grid-cols-3">
          {[t("feature1"), t("feature2"), t("feature3")].map((copy, index) => (
            <li
              key={index}
              className="rounded-[var(--radius-lg)] border bg-[var(--color-surface)] p-5 text-sm text-[var(--color-text-secondary)]"
            >
              {copy}
            </li>
          ))}
        </ul>

        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
          {INVESTIGATORS.map((investigator) => (
            <li
              key={investigator.callsign}
              className="rounded-[var(--radius-md)] border bg-[var(--color-surface-2)] p-3"
            >
              <span
                className="mb-2 block h-1.5 w-8 rounded-full"
                style={{ background: investigator.color }}
                aria-hidden
              />
              <p className="font-callsign text-sm">{investigator.displayName}</p>
              <p className="font-mono text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
                {investigator.role}
              </p>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
