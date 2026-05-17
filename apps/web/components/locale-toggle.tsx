"use client";

import { useTransition } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Languages } from "lucide-react";

import { Button } from "@/components/ui/button";
import { setLocale } from "@/app/actions/locale";

export function LocaleToggle() {
  const locale = useLocale();
  const t = useTranslations("common");
  const [isPending, startTransition] = useTransition();

  function toggle() {
    const next = locale === "es" ? "en" : "es";
    startTransition(() => {
      void setLocale(next);
    });
  }

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={toggle}
      disabled={isPending}
      aria-label={t("language")}
      className="font-mono uppercase"
    >
      <Languages className="mr-1.5 h-4 w-4" />
      {locale}
    </Button>
  );
}
