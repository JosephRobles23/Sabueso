import * as React from "react";
import type { InvestigatorCallsign } from "@sabueso/shared-types";

import { cn } from "@/lib/utils";

import { callsignColor, callsignDisplayName } from "./_meta";

export type AvatarVisualState = "normal" | "active" | "error";
export type AvatarSize = 48 | 64 | 96;

export interface InvestigatorAvatarProps extends React.HTMLAttributes<HTMLDivElement> {
  callsign: InvestigatorCallsign;
  size?: AvatarSize;
  state?: AvatarVisualState;
  withSpeechBubble?: boolean;
  speechText?: string;
  /** Override Dicebear style. Default: notionists. */
  avatarStyle?: "notionists" | "lorelei";
}

const RING_BY_STATE: Record<AvatarVisualState, string> = {
  normal: "ring-1 ring-[var(--color-border-default)]",
  active: "ring-2 ring-offset-2 ring-offset-[var(--color-canvas)]",
  error: "ring-2 ring-[var(--color-suspicious)] ring-offset-2 ring-offset-[var(--color-canvas)]",
};

function buildDicebearUrl(seed: string, style: "notionists" | "lorelei"): string {
  // Deterministic SVG avatar from the Dicebear public API. Seed = callsign so
  // every render of "el-contador" produces the same face.
  const params = new URLSearchParams({
    seed,
    backgroundType: "solid",
    backgroundColor: "transparent",
    radius: "50",
  });
  return `https://api.dicebear.com/9.x/${style}/svg?${params.toString()}`;
}

export const InvestigatorAvatar = React.forwardRef<HTMLDivElement, InvestigatorAvatarProps>(
  (
    {
      callsign,
      size = 64,
      state = "normal",
      withSpeechBubble = false,
      speechText,
      avatarStyle = "notionists",
      className,
      ...rest
    },
    ref,
  ) => {
    const color = callsignColor(callsign);
    const name = callsignDisplayName(callsign);
    const url = buildDicebearUrl(callsign, avatarStyle);

    const dimension = `${size}px`;
    const ring = RING_BY_STATE[state];

    return (
      <div ref={ref} className={cn("relative inline-flex flex-col items-center", className)} {...rest}>
        {withSpeechBubble && speechText ? (
          <div
            role="status"
            className={cn(
              "animate-bubble-pop pointer-events-none absolute -top-2 left-1/2 z-10 -translate-x-1/2 -translate-y-full",
              "max-w-[180px] rounded-[var(--radius-md)] border bg-[var(--color-paper)] px-2.5 py-1.5",
              "text-[11px] leading-tight text-[var(--color-text-paper)] shadow-sm",
              "font-mono",
            )}
            style={{ borderColor: "var(--color-border-default)" }}
          >
            <span className="line-clamp-2">{speechText.slice(0, 80)}</span>
            <span
              aria-hidden="true"
              className="absolute -bottom-1 left-1/2 h-2 w-2 -translate-x-1/2 rotate-45 border-r border-b bg-[var(--color-paper)]"
              style={{ borderColor: "var(--color-border-default)" }}
            />
          </div>
        ) : null}

        <div
          className={cn(
            "relative overflow-hidden rounded-full bg-[var(--color-surface-2)]",
            ring,
          )}
          style={{
            width: dimension,
            height: dimension,
            // Active state uses the callsign color for the ring.
            ...(state === "active" ? { boxShadow: `0 0 0 2px ${color}` } : {}),
          }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={url}
            alt={`Avatar de ${name}`}
            width={size}
            height={size}
            className="h-full w-full object-cover"
            loading="lazy"
            decoding="async"
          />
        </div>
      </div>
    );
  },
);
InvestigatorAvatar.displayName = "InvestigatorAvatar";
