"use client";

import * as React from "react";
import type { AgentStatus, InvestigatorCallsign } from "@sabueso/shared-types";

import { cn } from "@/lib/utils";

import { InvestigatorAvatar } from "./InvestigatorAvatar";
import { StatusPill } from "./StatusPill";
import { STATUS_META, callsignColor, callsignDisplayName, callsignRole } from "./_meta";

export interface InvestigatorWorkstationProps
  extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "onClick"> {
  callsign: InvestigatorCallsign;
  status: AgentStatus;
  /** Short detail rendered inside the status pill (truncated to 28 chars). */
  detail?: string;
  /** Optional speech bubble text above the avatar. */
  speechText?: string;
  onClick?: () => void;
}

export const InvestigatorWorkstation = React.forwardRef<
  HTMLButtonElement,
  InvestigatorWorkstationProps
>(({ callsign, status, detail, speechText, onClick, className, ...rest }, ref) => {
  const color = callsignColor(callsign);
  const name = callsignDisplayName(callsign);
  const role = callsignRole(callsign);
  const statusColor = STATUS_META[status].color;
  const visualState = status === "blocked" ? "error" : status === "idle" ? "normal" : "active";

  return (
    <button
      ref={ref}
      type="button"
      onClick={onClick}
      aria-label={`${name} — ${STATUS_META[status].label}`}
      className={cn(
        "group relative flex flex-col items-center gap-2 rounded-[var(--radius-md)] p-3",
        "transition-transform duration-150 hover:-translate-y-0.5 focus-visible:outline-none",
        "focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] focus-visible:ring-offset-2",
        "focus-visible:ring-offset-[var(--color-canvas)]",
        className,
      )}
      {...rest}
    >
      <div className="relative">
        {/* Tinted disc — radial glow at 25% opacity in the callsign color. */}
        <div
          aria-hidden="true"
          className="absolute top-1/2 left-1/2 h-[78px] w-[78px] -translate-x-1/2 -translate-y-1/2 rounded-full blur-md"
          style={{
            background: `radial-gradient(closest-side, ${color}40, transparent 70%)`,
          }}
        />
        <div
          aria-hidden="true"
          className="absolute top-1/2 left-1/2 h-[60px] w-[60px] -translate-x-1/2 -translate-y-1/2 rounded-full"
          style={{ backgroundColor: `color-mix(in srgb, ${color} 25%, transparent)` }}
        />

        {/* Avatar lifted slightly above the disc. */}
        <div className="relative -translate-y-1">
          <InvestigatorAvatar
            callsign={callsign}
            size={48}
            state={visualState}
            withSpeechBubble={Boolean(speechText)}
            speechText={speechText}
          />
        </div>
      </div>

      {/* Name placard with bottom border in callsign color + pulsing LED. */}
      <div
        className="flex items-center gap-1.5 rounded-[var(--radius-sm)] border-b-2 bg-[var(--color-surface-2)] px-2 py-1"
        style={{ borderBottomColor: color }}
      >
        <span
          aria-hidden="true"
          className={cn(
            "h-1.5 w-1.5 rounded-full",
            status !== "idle" ? "animate-pulse-led" : "",
          )}
          style={{ color: statusColor, backgroundColor: statusColor }}
        />
        <span className="font-callsign text-[13px] leading-none text-[var(--color-text-primary)]">
          {name}
        </span>
      </div>

      <StatusPill status={status} detail={detail} />

      {role ? (
        <span className="font-mono text-[10px] tracking-tight text-[var(--color-text-muted)]">
          {role.toUpperCase()}
        </span>
      ) : null}
    </button>
  );
});
InvestigatorWorkstation.displayName = "InvestigatorWorkstation";
