import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { CountrySelector } from "@/components/CountrySelector";
import { LocaleToggle } from "@/components/locale-toggle";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { getCountry } from "@/lib/country";
import { getCurrentUser } from "@/lib/supabase/server";

export async function Nav({ variant = "app" }: { variant?: "marketing" | "app" }) {
  const [t, user, country] = await Promise.all([
    getTranslations("common"),
    getCurrentUser(),
    getCountry(),
  ]);

  return (
    <header className="sticky top-0 z-30 border-b border-[var(--color-border-default)] bg-[var(--color-canvas)]/85 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
        <Link href={variant === "marketing" ? "/" : "/app"} className="flex items-center gap-2">
          <span aria-hidden className="text-2xl leading-none">🐕‍🦺</span>
          <span className="font-display text-lg tracking-tight">{t("appName")}</span>
        </Link>

        <div className="flex items-center gap-1">
          {variant === "app" && <CountrySelector initialCountry={country} />}
          <LocaleToggle />
          <ThemeToggle />
          {user ? (
            <span
              className="ml-2 inline-flex h-8 items-center justify-center rounded-[var(--radius-full)] bg-[var(--color-surface-2)] px-3 text-xs"
              title={user.email ?? undefined}
            >
              {user.email?.[0]?.toUpperCase() ?? "·"}
            </span>
          ) : (
            <Button asChild size="sm" variant="outline" className="ml-2">
              <Link href="/auth/login">{t("login")}</Link>
            </Button>
          )}
        </div>
      </div>
    </header>
  );
}
