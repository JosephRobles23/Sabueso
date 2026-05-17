import * as React from "react";

import { cn } from "@/lib/utils";

export type EvidenceSourceType = "jne" | "seace" | "sunarp" | "news" | "legalize" | "other";

export interface EvidenceChipProps extends Omit<React.AnchorHTMLAttributes<HTMLAnchorElement>, "type"> {
  sourceUrl: string;
  sourceType?: EvidenceSourceType;
  /** Optional label override; defaults to the source type label or the host. */
  label?: string;
  size?: "sm" | "md";
}

const SOURCE_LABELS: Record<EvidenceSourceType, string> = {
  jne: "JNE",
  seace: "SEACE",
  sunarp: "SUNARP",
  news: "Prensa",
  legalize: "Legalize",
  other: "Fuente",
};

const SOURCE_TINT: Record<EvidenceSourceType, string> = {
  jne: "var(--color-discovered)",
  seace: "var(--color-contador)",
  sunarp: "var(--color-tasadora)",
  news: "var(--color-periodista)",
  legalize: "var(--color-letrado)",
  other: "var(--color-text-secondary)",
};

function hostFromUrl(url: string): string {
  try {
    return new URL(url).host.replace(/^www\./, "");
  } catch {
    return url;
  }
}

function faviconUrl(url: string): string | null {
  const host = hostFromUrl(url);
  if (!host || host === url) return null;
  return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(host)}&sz=32`;
}

export const EvidenceChip = React.forwardRef<HTMLAnchorElement, EvidenceChipProps>(
  ({ sourceUrl, sourceType = "other", label, size = "sm", className, ...rest }, ref) => {
    const host = hostFromUrl(sourceUrl);
    const favicon = faviconUrl(sourceUrl);
    const displayLabel = label ?? SOURCE_LABELS[sourceType];
    const tint = SOURCE_TINT[sourceType];

    return (
      <a
        ref={ref}
        href={sourceUrl}
        target="_blank"
        rel="noopener noreferrer"
        title={host}
        aria-label={`Fuente ${displayLabel} — ${host} (abre en nueva pestaña)`}
        className={cn(
          "group inline-flex items-center gap-1.5 rounded-full border bg-[var(--color-surface-2)]",
          "text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-paper)]",
          "hover:text-[var(--color-text-primary)] focus-visible:outline-none focus-visible:ring-2",
          "focus-visible:ring-[var(--color-accent)] focus-visible:ring-offset-2",
          "focus-visible:ring-offset-[var(--color-canvas)]",
          size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-xs",
          className,
        )}
        style={{
          borderColor: `color-mix(in srgb, ${tint} 30%, var(--color-border-default))`,
        }}
        {...rest}
      >
        {favicon ? (
          /* eslint-disable-next-line @next/next/no-img-element */
          <img
            src={favicon}
            alt=""
            width={12}
            height={12}
            className="h-3 w-3 rounded-sm"
            loading="lazy"
            decoding="async"
          />
        ) : (
          <span
            aria-hidden="true"
            className="h-2 w-2 rounded-full"
            style={{ backgroundColor: tint }}
          />
        )}
        <span className="font-mono leading-none">{displayLabel}</span>
        <span aria-hidden="true" className="text-[var(--color-text-muted)]">
          ↗
        </span>
      </a>
    );
  },
);
EvidenceChip.displayName = "EvidenceChip";
