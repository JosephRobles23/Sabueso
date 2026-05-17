import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { SearchInput } from "@/components/search-input";
import { api } from "@/lib/api";
import type { InvestigationSummary } from "@/lib/api";

async function safeListRecent(): Promise<InvestigationSummary[]> {
  try {
    return await api.listRecent();
  } catch {
    return [];
  }
}

const TRENDING = [
  { id: "trend-1", emoji: "🏛️", label: "Candidatos presidenciales 2026" },
  { id: "trend-2", emoji: "🔥", label: "MINSA contratos 2024" },
  { id: "trend-3", emoji: "📑", label: "Gobiernos regionales · obras" },
];

export default async function HomePage() {
  const [t, tCommon, recent] = await Promise.all([
    getTranslations("app"),
    getTranslations("common"),
    safeListRecent(),
  ]);

  return (
    <main className="mx-auto max-w-3xl space-y-12 px-6 py-12 sm:py-20">
      <section className="space-y-4 text-center">
        <h1 className="font-display text-5xl tracking-tight sm:text-6xl">{tCommon("appName")}</h1>
        <p className="text-[var(--color-text-secondary)]">{tCommon("tagline")}</p>
      </section>

      <SearchInput />

      <section className="space-y-3">
        <p className="font-mono text-[11px] uppercase tracking-wider text-[var(--color-text-muted)]">
          {t("trending")}
        </p>
        <ul className="flex flex-wrap gap-2">
          {TRENDING.map((trend) => (
            <li key={trend.id}>
              <button
                type="button"
                className="rounded-[var(--radius-full)] border border-[var(--color-border-default)] bg-[var(--color-surface)] px-3 py-1.5 text-sm transition-colors hover:bg-[var(--color-surface-2)]"
              >
                <span className="mr-1.5" aria-hidden>
                  {trend.emoji}
                </span>
                {trend.label}
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section className="space-y-3">
        <p className="font-mono text-[11px] uppercase tracking-wider text-[var(--color-text-muted)]">
          {t("recent")}
        </p>
        {recent.length === 0 ? (
          <p className="text-sm text-[var(--color-text-secondary)]">{t("noRecent")}</p>
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {recent.map((item) => (
              <li key={item.id}>
                <Link href={`/i/${item.id}`} className="block focus-visible:outline-none">
                  <Card className="h-full transition-shadow hover:shadow-md">
                    <CardHeader>
                      <CardTitle className="line-clamp-2">{item.target_name}</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="font-mono text-[11px] uppercase text-[var(--color-text-muted)]">
                        {item.status}
                      </p>
                    </CardContent>
                    <CardFooter className="flex items-center justify-between">
                      <span className="font-mono text-[11px] text-[var(--color-text-muted)]">
                        {item.lead_count} pistas
                      </span>
                      <span className="font-mono text-[11px] text-[var(--color-text-muted)]">
                        {Math.round(item.progress_pct)}%
                      </span>
                    </CardFooter>
                  </Card>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
