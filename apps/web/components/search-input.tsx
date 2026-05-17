"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useId, useState } from "react";

import { Input } from "@/components/ui/input";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { api, type SearchHit } from "@/lib/api";

const DEBOUNCE_MS = 200;
const MAX_RESULTS = 10;

function highlight(text: string, query: string) {
  if (!query) return text;
  const i = text.toLowerCase().indexOf(query.toLowerCase());
  if (i < 0) return text;
  return (
    <>
      {text.slice(0, i)}
      <mark className="bg-[var(--color-accent)]/20 text-[var(--color-text-primary)]">
        {text.slice(i, i + query.length)}
      </mark>
      {text.slice(i + query.length)}
    </>
  );
}

export function SearchInput() {
  const t = useTranslations("app");
  const inputId = useId();
  const [query, setQuery] = useState("");
  const debounced = useDebouncedValue(query, DEBOUNCE_MS);
  const trimmed = debounced.trim();

  const { data, isFetching } = useQuery({
    queryKey: ["search", trimmed],
    queryFn: ({ signal }) => api.search(trimmed, "pe", signal),
    enabled: trimmed.length >= 2,
    staleTime: 30_000,
  });

  const hits: SearchHit[] = (data?.hits ?? []).slice(0, MAX_RESULTS);
  const showResults = trimmed.length >= 2;

  return (
    <div className="space-y-3">
      <label htmlFor={inputId} className="sr-only">
        {t("searchPlaceholder")}
      </label>

      <div className="relative">
        <Search
          className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]"
          size={18}
          aria-hidden
        />
        <Input
          id={inputId}
          autoFocus
          autoComplete="off"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t("searchPlaceholder")}
          className="h-14 rounded-[var(--radius-lg)] border-[var(--color-border-strong)] pl-12 pr-16 text-base"
        />
        <kbd className="absolute right-4 top-1/2 hidden -translate-y-1/2 select-none rounded-[var(--radius-sm)] border border-[var(--color-border-default)] bg-[var(--color-surface-2)] px-2 py-0.5 font-mono text-[11px] uppercase text-[var(--color-text-secondary)] sm:inline">
          {t("kbdHint")}
        </kbd>
      </div>

      <p className="font-mono text-[11px] text-[var(--color-text-muted)]">{t("searchHint")}</p>

      {showResults && (
        <div
          role="listbox"
          aria-busy={isFetching || undefined}
          className="overflow-hidden rounded-[var(--radius-lg)] border bg-[var(--color-surface)] shadow-sm"
        >
          {hits.length === 0 && !isFetching && (
            <p className="px-4 py-6 text-sm text-[var(--color-text-secondary)]">
              {t("noResults")}
            </p>
          )}
          <ul className="divide-y divide-[var(--color-border-default)]">
            {hits.map((hit) => (
              <li key={hit.id}>
                <Link
                  href={`/i/${hit.id}`}
                  className="flex items-center justify-between px-4 py-3 transition-colors hover:bg-[var(--color-surface-2)]"
                  role="option"
                >
                  <span className="text-sm">{highlight(hit.name, trimmed)}</span>
                  {hit.identifier && (
                    <span className="font-mono text-[11px] uppercase text-[var(--color-text-muted)]">
                      {hit.identifier}
                    </span>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
