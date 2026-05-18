"use client";

/**
 * PreviewModeBanner — banner amarillo "Modo preview · datos limitados" (S-18).
 *
 * Aparece si **cualquiera** de estas condiciones se cumple:
 *  1. La cookie de país != "pe" (control client-side, deep-linkable).
 *  2. Algún InvestigationEvent con type="preview_mode_warning" llegó por SSE
 *     o por replay — el worker lo emite cuando el plan corre el subset
 *     reducido.
 *
 * El banner muestra el país detectado y, si el evento trajo payload, las
 * fuentes disponibles + investigadores activos para que el usuario entienda
 * por qué hay menos hallazgos.
 */
import * as React from "react";
import { TriangleAlert } from "lucide-react";

import { COUNTRIES, readCountryCookie } from "@/lib/country";
import type { Country, InvestigationEvent, PreviewModeWarningPayload } from "@sabueso/shared-types";

export interface PreviewModeBannerProps {
  /** Opcional: si se pasa, evita la lectura cliente del cookie. */
  country?: Country;
  /** Opcional: si se pasan eventos, el banner busca preview_mode_warning. */
  events?: InvestigationEvent[];
}

export function PreviewModeBanner({ country: forced, events }: PreviewModeBannerProps) {
  const [cookieCountry, setCookieCountry] = React.useState<Country | null>(null);

  React.useEffect(() => {
    if (forced) return;
    setCookieCountry(readCountryCookie());

    function onChange(e: Event) {
      const detail = (e as CustomEvent<Country>).detail;
      if (detail) setCookieCountry(detail);
    }
    window.addEventListener("sabueso:country:change", onChange);
    return () => window.removeEventListener("sabueso:country:change", onChange);
  }, [forced]);

  const country = forced ?? cookieCountry ?? "pe";

  // Sólo escaneamos los últimos 50 eventos para barato — un demo replay
  // tiene <30 eventos, una investigación real <500.
  const warning = React.useMemo(() => {
    if (!events || events.length === 0) return null;
    const window = events.slice(-50);
    for (let i = window.length - 1; i >= 0; i--) {
      const e = window[i]!;
      if (e.type === "preview_mode_warning") {
        return e.payload as unknown as PreviewModeWarningPayload;
      }
    }
    return null;
  }, [events]);

  const fromCookie = country !== "pe";
  if (!fromCookie && !warning) return null;

  const meta = COUNTRIES.find((c) => c.code === country) ?? COUNTRIES[0]!;

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex flex-col gap-1 border-b border-[var(--color-ambiguous)]/30 bg-[color-mix(in_srgb,var(--color-ambiguous)_18%,transparent)] px-4 py-2 text-xs text-[var(--color-text-primary)] lg:px-6"
    >
      <div className="flex items-center gap-2">
        <TriangleAlert className="h-3.5 w-3.5 text-[var(--color-ambiguous)]" aria-hidden />
        <strong className="font-mono uppercase tracking-wider text-[10px] text-[var(--color-ambiguous)]">
          Modo preview · datos limitados
        </strong>
        <span aria-hidden>{meta.flag}</span>
        <span className="text-[var(--color-text-secondary)]">{meta.name}</span>
      </div>
      {warning && (
        <p className="ml-5 text-[var(--color-text-secondary)]">
          Sólo {warning.active_investigators.length} investigadores activos
          {warning.available_sources.length > 0 && (
            <>
              {" · fuentes: "}
              <span className="font-mono text-[10px] uppercase">
                {warning.available_sources.slice(0, 4).join(", ")}
                {warning.available_sources.length > 4 && "…"}
              </span>
            </>
          )}
          {warning.message && <span>{". " + warning.message}</span>}
        </p>
      )}
    </div>
  );
}
