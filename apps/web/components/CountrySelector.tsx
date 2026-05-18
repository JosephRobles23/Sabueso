"use client";

/**
 * CountrySelector — dropdown del navbar con 4 países (S-18).
 *
 * - Lee el país inicial de cookie + URL `?c=<code>` (URL gana sobre cookie).
 * - Persiste la selección en cookie. NO empuja el cambio a la URL automáticamente
 *   para evitar reloads de toda la app — el banner Preview reacciona via cookie.
 * - Default: pe.
 */
import * as React from "react";
import { ChevronDown } from "lucide-react";

import { cn } from "@/lib/utils";
import {
  COUNTRIES,
  COUNTRY_COOKIE,
  normalizeCountry,
  writeCountryCookie,
} from "@/lib/country";
import type { Country } from "@sabueso/shared-types";

export interface CountrySelectorProps {
  initialCountry: Country;
}

export function CountrySelector({ initialCountry }: CountrySelectorProps) {
  const [country, setCountry] = React.useState<Country>(initialCountry);
  const [open, setOpen] = React.useState(false);
  const wrapperRef = React.useRef<HTMLDivElement>(null);

  // En el mount cliente: si la URL trae ?c=<code>, tiene prioridad sobre la
  // cookie (deep-linking de demos: /app?c=cl entra siempre en modo Chile).
  React.useEffect(() => {
    if (typeof window === "undefined") return;
    const url = new URL(window.location.href);
    const fromUrl = url.searchParams.get("c");
    if (fromUrl) {
      const next = normalizeCountry(fromUrl);
      if (next !== country) {
        setCountry(next);
        writeCountryCookie(next);
      }
    }
  }, []); // sólo en mount

  React.useEffect(() => {
    if (!open) return;
    function onClick(e: MouseEvent) {
      if (!wrapperRef.current) return;
      if (!wrapperRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const active = COUNTRIES.find((c) => c.code === country) ?? COUNTRIES[0]!;

  function change(next: Country) {
    setCountry(next);
    writeCountryCookie(next);
    setOpen(false);
    // Refrescar el árbol RSC para que /app y /i/[id] vuelvan a leer la cookie
    // y rehagan los banners. Cookie + soft refresh > full reload.
    if (typeof window !== "undefined") {
      // window.location.reload sería brutal; preferimos un soft refresh.
      // Como no exportamos un router hook aquí, escribimos un evento custom
      // que /app/page.tsx escucha en montaje y refresca el server tree.
      window.dispatchEvent(new CustomEvent(`${COUNTRY_COOKIE}:change`, { detail: next }));
    }
  }

  return (
    <div ref={wrapperRef} className="relative inline-block">
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={`País: ${active.name}`}
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-1.5 rounded-[var(--radius-md)] border border-[var(--color-border-default)] bg-[var(--color-surface)] px-2 py-1 text-sm transition-colors hover:bg-[var(--color-surface-2)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]"
      >
        <span aria-hidden className="text-base leading-none">{active.flag}</span>
        <span className="font-mono text-[11px] uppercase tracking-wider text-[var(--color-text-secondary)]">
          {active.code}
        </span>
        <ChevronDown className="h-3 w-3 text-[var(--color-text-muted)]" aria-hidden />
      </button>

      {open && (
        <ul
          role="listbox"
          aria-label="Seleccionar país"
          className="absolute right-0 z-30 mt-1 w-44 overflow-hidden rounded-[var(--radius-md)] border border-[var(--color-border-strong)] bg-[var(--color-surface)] shadow-lg"
        >
          {COUNTRIES.map((c) => {
            const selected = c.code === country;
            return (
              <li key={c.code}>
                <button
                  type="button"
                  role="option"
                  aria-selected={selected}
                  onClick={() => change(c.code)}
                  className={cn(
                    "flex w-full items-center justify-between gap-2 px-3 py-1.5 text-sm transition-colors hover:bg-[var(--color-surface-2)]",
                    selected && "bg-[var(--color-surface-2)]",
                  )}
                >
                  <span className="flex items-center gap-2">
                    <span aria-hidden>{c.flag}</span>
                    <span>{c.name}</span>
                  </span>
                  {!c.firstClass && (
                    <span className="font-mono text-[9px] uppercase tracking-wider text-[var(--color-ambiguous)]">
                      preview
                    </span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
