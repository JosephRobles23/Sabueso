"use client";

/**
 * Lightweight AI-Elements-style primitives.
 *
 * The real `ai-elements` package would normally be installed via
 * `npx ai-elements@latest add conversation message reasoning tool source response`,
 * which scaffolds shadcn-style components into `components/ai-elements/`. We
 * keep the same conceptual API (Conversation > Message; Reasoning, Tool,
 * Source, Response as primitives) so swap-in later is mechanical.
 */

import * as React from "react";
import { ChevronRight } from "lucide-react";

import { cn } from "@/lib/utils";

// ─────────────────────────────────────────────────────────────────────────────
// Conversation — scrollable thread container
// ─────────────────────────────────────────────────────────────────────────────

export interface ConversationProps extends React.HTMLAttributes<HTMLDivElement> {}

export const Conversation = React.forwardRef<HTMLDivElement, ConversationProps>(
  ({ className, children, ...props }, ref) => (
    <div
      ref={ref}
      role="log"
      aria-live="polite"
      className={cn(
        "flex flex-col gap-3 overflow-y-auto px-1 py-2",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  ),
);
Conversation.displayName = "Conversation";

// ─────────────────────────────────────────────────────────────────────────────
// Message — single bubble. Authored side ("user") aligns right.
// ─────────────────────────────────────────────────────────────────────────────

export interface MessageProps extends React.HTMLAttributes<HTMLDivElement> {
  from: "agent" | "user" | "system";
  /** Avatar element rendered on the left of the bubble. */
  avatar?: React.ReactNode;
  /** Color tint for the bubble border / header. Defaults to accent. */
  accentColor?: string;
  /** Author label shown above the bubble. */
  author?: string;
  /** Optional timestamp string ("14:02"). */
  timestamp?: string;
}

export const Message = React.forwardRef<HTMLDivElement, MessageProps>(
  ({ from, avatar, accentColor, author, timestamp, className, children, ...props }, ref) => {
    const isUser = from === "user";
    const tint = accentColor ?? "var(--color-accent)";
    return (
      <div
        ref={ref}
        className={cn(
          "flex items-start gap-2",
          isUser ? "flex-row-reverse" : "flex-row",
          className,
        )}
        {...props}
      >
        {avatar ? <div className="flex-none">{avatar}</div> : null}
        <div className={cn("min-w-0 max-w-[85%] flex-1", isUser && "text-right")}>
          {author || timestamp ? (
            <div
              className={cn(
                "mb-0.5 flex items-baseline gap-2 text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]",
                isUser && "justify-end",
              )}
            >
              {author ? (
                <span className="font-callsign text-[11px] normal-case tracking-normal" style={{ color: tint }}>
                  {author}
                </span>
              ) : null}
              {timestamp ? <span className="font-mono">{timestamp}</span> : null}
            </div>
          ) : null}
          <div
            className={cn(
              "rounded-[var(--radius-md)] border px-3 py-2 text-sm leading-relaxed",
              "bg-[var(--color-surface)] text-[var(--color-text-primary)]",
            )}
            style={{ borderColor: `color-mix(in srgb, ${tint} 35%, var(--color-border-default))` }}
          >
            {children}
          </div>
        </div>
      </div>
    );
  },
);
Message.displayName = "Message";

// ─────────────────────────────────────────────────────────────────────────────
// Reasoning — collapsible "thinking out loud" block
// ─────────────────────────────────────────────────────────────────────────────

export interface ReasoningProps extends React.HTMLAttributes<HTMLDetailsElement> {
  title?: string;
  defaultOpen?: boolean;
}

export const Reasoning = React.forwardRef<HTMLDetailsElement, ReasoningProps>(
  ({ title = "Razonamiento", defaultOpen = false, className, children, ...props }, ref) => (
    <details
      ref={ref}
      open={defaultOpen}
      className={cn(
        "group rounded-[var(--radius-md)] border border-dashed bg-[var(--color-surface-2)]",
        "border-[var(--color-border-default)]",
        className,
      )}
      {...props}
    >
      <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2 font-mono text-[11px] uppercase tracking-wider text-[var(--color-text-secondary)]">
        <ChevronRight className="h-3 w-3 transition-transform group-open:rotate-90" aria-hidden />
        <span>{title}</span>
      </summary>
      <div className="border-t border-dashed border-[var(--color-border-default)] px-3 py-2 text-xs leading-relaxed text-[var(--color-text-secondary)]">
        {children}
      </div>
    </details>
  ),
);
Reasoning.displayName = "Reasoning";

// ─────────────────────────────────────────────────────────────────────────────
// Tool — collapsible tool-call display
// ─────────────────────────────────────────────────────────────────────────────

export interface ToolProps extends React.HTMLAttributes<HTMLDetailsElement> {
  name: string;
  status?: "running" | "ok" | "error" | "cache_hit";
  durationMs?: number | null;
  args?: Record<string, unknown>;
  result?: unknown;
}

const STATUS_LABEL: Record<NonNullable<ToolProps["status"]>, string> = {
  running: "ejecutando",
  ok: "ok",
  error: "error",
  cache_hit: "cache",
};

const STATUS_COLOR: Record<NonNullable<ToolProps["status"]>, string> = {
  running: "var(--color-ambiguous)",
  ok: "var(--color-declared)",
  error: "var(--color-suspicious)",
  cache_hit: "var(--color-discovered)",
};

export const Tool = React.forwardRef<HTMLDetailsElement, ToolProps>(
  ({ name, status = "ok", durationMs, args, result, className, ...props }, ref) => {
    const color = STATUS_COLOR[status];
    return (
      <details
        ref={ref}
        className={cn(
          "group rounded-[var(--radius-sm)] border bg-[var(--color-surface)] font-mono text-[11px]",
          className,
        )}
        style={{ borderColor: `color-mix(in srgb, ${color} 35%, var(--color-border-default))` }}
        {...props}
      >
        <summary className="flex cursor-pointer list-none items-center gap-2 px-2 py-1.5">
          <ChevronRight className="h-3 w-3 transition-transform group-open:rotate-90" aria-hidden />
          <span className="text-[var(--color-text-primary)]">{name}</span>
          <span
            className="ml-auto inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] uppercase"
            style={{
              color,
              backgroundColor: `color-mix(in srgb, ${color} 12%, transparent)`,
            }}
          >
            {STATUS_LABEL[status]}
          </span>
          {typeof durationMs === "number" ? (
            <span className="text-[var(--color-text-muted)]">{durationMs}ms</span>
          ) : null}
        </summary>
        <div className="space-y-1 border-t border-[var(--color-border-default)] px-2 py-1.5 text-[var(--color-text-secondary)]">
          {args ? (
            <pre className="overflow-x-auto whitespace-pre-wrap break-all text-[10px]">
              {JSON.stringify(args, null, 2)}
            </pre>
          ) : null}
          {result !== undefined ? (
            <pre className="overflow-x-auto whitespace-pre-wrap break-all text-[10px]">
              → {typeof result === "string" ? result : JSON.stringify(result, null, 2)}
            </pre>
          ) : null}
        </div>
      </details>
    );
  },
);
Tool.displayName = "Tool";

// ─────────────────────────────────────────────────────────────────────────────
// Source — citation chip (composed in callers from EvidenceChip when possible)
// ─────────────────────────────────────────────────────────────────────────────

export interface SourceProps extends React.HTMLAttributes<HTMLDivElement> {}

export const Source = React.forwardRef<HTMLDivElement, SourceProps>(
  ({ className, children, ...props }, ref) => (
    <div ref={ref} className={cn("flex flex-wrap items-center gap-1.5", className)} {...props}>
      {children}
    </div>
  ),
);
Source.displayName = "Source";

// ─────────────────────────────────────────────────────────────────────────────
// Response — plain prose body for an AI reply
// ─────────────────────────────────────────────────────────────────────────────

export interface ResponseProps extends React.HTMLAttributes<HTMLDivElement> {}

export const Response = React.forwardRef<HTMLDivElement, ResponseProps>(
  ({ className, children, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "prose prose-sm max-w-none text-sm leading-relaxed text-[var(--color-text-primary)]",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  ),
);
Response.displayName = "Response";
