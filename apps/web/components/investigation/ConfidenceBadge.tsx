import * as React from "react";

import { cn } from "@/lib/utils";

export interface ConfidenceBadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  /** Confidence in [0, 1] — matches Claim.confidence shape from shared-types. */
  value: number;
  size?: "sm" | "md";
  /** When true, renders the leading check glyph. Default true. */
  withGlyph?: boolean;
}

const HIGH_THRESHOLD = 0.85;
const MID_THRESHOLD = 0.6;

function colorForConfidence(value: number): string {
  if (value >= HIGH_THRESHOLD) return "var(--color-declared)";
  if (value >= MID_THRESHOLD) return "var(--color-ambiguous)";
  return "var(--color-suspicious)";
}

export const ConfidenceBadge = React.forwardRef<HTMLSpanElement, ConfidenceBadgeProps>(
  ({ value, size = "sm", withGlyph = true, className, ...rest }, ref) => {
    const clamped = Math.max(0, Math.min(1, value));
    const pct = Math.round(clamped * 100);
    const color = colorForConfidence(clamped);
    const glyph = clamped >= HIGH_THRESHOLD ? "✓" : clamped >= MID_THRESHOLD ? "~" : "!";

    return (
      <span
        ref={ref}
        aria-label={`Confianza ${pct} sobre 100`}
        className={cn(
          "inline-flex items-center gap-1 rounded-[var(--radius-sm)] border font-mono tabular-nums",
          size === "sm" ? "px-1.5 py-0.5 text-[11px]" : "px-2 py-0.5 text-xs",
          className,
        )}
        style={{
          color,
          backgroundColor: `color-mix(in srgb, ${color} 10%, transparent)`,
          borderColor: `color-mix(in srgb, ${color} 35%, transparent)`,
        }}
        {...rest}
      >
        {withGlyph ? (
          <span aria-hidden="true" className="leading-none">
            {glyph}
          </span>
        ) : null}
        <span>{pct}</span>
      </span>
    );
  },
);
ConfidenceBadge.displayName = "ConfidenceBadge";
