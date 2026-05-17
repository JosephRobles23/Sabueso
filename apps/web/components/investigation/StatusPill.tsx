import * as React from "react";
import type { AgentStatus } from "@sabueso/shared-types";

import { cn } from "@/lib/utils";

import { STATUS_META } from "./_meta";

export interface StatusPillProps extends React.HTMLAttributes<HTMLSpanElement> {
  status: AgentStatus;
  /** Optional detail appended after the status label (truncated to 28 chars). */
  detail?: string;
  size?: "sm" | "md";
}

const ThinkingDots = () => (
  <span aria-hidden="true" className="inline-flex items-center gap-[2px] pl-1">
    <span className="h-1 w-1 animate-bounce rounded-full bg-current [animation-delay:-0.3s]" />
    <span className="h-1 w-1 animate-bounce rounded-full bg-current [animation-delay:-0.15s]" />
    <span className="h-1 w-1 animate-bounce rounded-full bg-current" />
  </span>
);

export const StatusPill = React.forwardRef<HTMLSpanElement, StatusPillProps>(
  ({ status, detail, size = "sm", className, ...rest }, ref) => {
    const meta = STATUS_META[status];

    const truncatedDetail = detail && detail.length > 28 ? `${detail.slice(0, 28)}…` : detail;

    return (
      <span
        ref={ref}
        role="status"
        aria-label={`${meta.label}${truncatedDetail ? `: ${truncatedDetail}` : ""}`}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full border font-mono",
          size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-xs",
          className,
        )}
        style={{
          color: meta.color,
          backgroundColor: `color-mix(in srgb, ${meta.color} 12%, transparent)`,
          borderColor: `color-mix(in srgb, ${meta.color} 30%, transparent)`,
        }}
        {...rest}
      >
        <span
          aria-hidden="true"
          className={cn(
            "h-1.5 w-1.5 rounded-full",
            status === "thinking" || status === "working" ? "animate-pulse" : "",
          )}
          style={{ backgroundColor: meta.color }}
        />
        <span>{meta.label}</span>
        {truncatedDetail ? (
          <>
            <span aria-hidden="true" className="opacity-60">
              ·
            </span>
            <span className="truncate">{truncatedDetail}</span>
          </>
        ) : null}
        {status === "thinking" ? <ThinkingDots /> : null}
      </span>
    );
  },
);
StatusPill.displayName = "StatusPill";
