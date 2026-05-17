"use client";

/**
 * DossierPanel — right-most panel. Renders the dossier markdown with two
 * inline custom tags processed *before* react-markdown sees them:
 *
 *   <conf v="0.84" />                → <ConfidenceBadge value={0.84} />
 *   <src url="https://…" type="jne"/> → <EvidenceChip sourceUrl=… sourceType="jne" />
 *
 * react-markdown by default strips raw HTML and `rehype-raw` is not in deps,
 * so we substitute these tags into invisible marker strings, render, then
 * walk the React children and replace the markers with the actual atoms.
 *
 * Live-stream: pass `streaming` to add a blinking caret at the end while
 * the synthesizer is still writing.
 */

import * as React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize from "rehype-sanitize";

import { cn } from "@/lib/utils";

import { ConfidenceBadge } from "./ConfidenceBadge";
import { EvidenceChip, type EvidenceSourceType } from "./EvidenceChip";

export interface DossierPanelProps {
  dossier_md: string;
  streaming?: boolean;
  className?: string;
}

const CONF_TAG_RE = /<conf\s+v="([\d.]+)"\s*\/>/g;
const SRC_TAG_RE = /<src\s+url="([^"]+)"(?:\s+type="([^"]+)")?\s*\/>/g;

// Use a no-print unicode separator that markdown won't touch.
const SEP = "⁣";
const CONF_MARK = `${SEP}CONF`;
const SRC_MARK = `${SEP}SRC`;
const MARK_RE = new RegExp(
  `${SEP}CONF:([\\d.]+)${SEP}|${SEP}SRC:([^|]+)\\|([^${SEP}]+)${SEP}`,
  "g",
);

function preprocess(md: string): string {
  return md
    .replace(CONF_TAG_RE, (_m, v) => `${CONF_MARK}:${v}${SEP}`)
    .replace(SRC_TAG_RE, (_m, url, type) => `${SRC_MARK}:${url}|${type ?? "other"}${SEP}`);
}

function substitute(children: React.ReactNode): React.ReactNode {
  return React.Children.map(children, (child, index) => {
    if (typeof child === "string") {
      const parts: React.ReactNode[] = [];
      let lastIndex = 0;
      let m: RegExpExecArray | null;
      const re = new RegExp(MARK_RE);
      let i = 0;
      while ((m = re.exec(child)) !== null) {
        if (m.index > lastIndex) parts.push(child.slice(lastIndex, m.index));
        if (m[1] !== undefined) {
          parts.push(
            <ConfidenceBadge
              key={`conf-${index}-${i}`}
              value={Number(m[1])}
              className="mx-1 align-middle"
            />,
          );
        } else if (m[2] !== undefined && m[3] !== undefined) {
          parts.push(
            <EvidenceChip
              key={`src-${index}-${i}`}
              sourceUrl={m[2]}
              sourceType={m[3] as EvidenceSourceType}
              className="mx-1 align-middle"
            />,
          );
        }
        i++;
        lastIndex = m.index + m[0].length;
      }
      if (lastIndex === 0) return child;
      if (lastIndex < child.length) parts.push(child.slice(lastIndex));
      return parts;
    }
    if (React.isValidElement(child)) {
      const props = child.props as { children?: React.ReactNode };
      if (props.children) {
        return React.cloneElement(
          child,
          { key: child.key ?? index } as Record<string, unknown>,
          substitute(props.children),
        );
      }
    }
    return child;
  });
}

function withMarkers<T extends { children?: React.ReactNode }>(
  Component: keyof React.JSX.IntrinsicElements,
) {
  const Wrapper = ({ children, ...rest }: T) =>
    React.createElement(Component, rest as Record<string, unknown>, substitute(children));
  Wrapper.displayName = `WithMarkers(${String(Component)})`;
  return Wrapper;
}

export function DossierPanel({ dossier_md, streaming, className }: DossierPanelProps) {
  const processed = React.useMemo(() => preprocess(dossier_md), [dossier_md]);

  return (
    <section
      aria-label="Dossier"
      className={cn(
        "flex h-full min-h-0 flex-col rounded-[var(--radius-lg)] border bg-[var(--color-surface)]",
        className,
      )}
    >
      <header className="flex items-baseline justify-between border-b border-[var(--color-border-default)] px-4 py-3">
        <h2 className="font-display text-lg">Dossier</h2>
        {streaming ? (
          <span className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-wider text-[var(--color-accent)]">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--color-accent)]" />
            redactando
          </span>
        ) : (
          <span className="font-mono text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
            preview
          </span>
        )}
      </header>

      <article
        aria-live={streaming ? "polite" : undefined}
        className={cn(
          "min-h-0 flex-1 overflow-y-auto px-5 py-4",
          "prose prose-sm max-w-none",
          "prose-headings:font-display prose-headings:tracking-tight prose-headings:text-[var(--color-text-primary)]",
          "prose-p:text-[var(--color-text-primary)] prose-p:leading-relaxed",
          "prose-strong:text-[var(--color-text-primary)]",
          "prose-blockquote:border-l-[var(--color-accent)] prose-blockquote:text-[var(--color-text-secondary)]",
          "prose-code:font-mono prose-code:text-[var(--color-text-primary)] prose-code:before:hidden prose-code:after:hidden",
          "prose-li:text-[var(--color-text-primary)]",
        )}
      >
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeSanitize]}
          components={{
            p: withMarkers("p"),
            li: withMarkers("li"),
            td: withMarkers("td"),
            h1: withMarkers("h1"),
            h2: withMarkers("h2"),
            h3: withMarkers("h3"),
            h4: withMarkers("h4"),
            blockquote: withMarkers("blockquote"),
          }}
        >
          {processed}
        </ReactMarkdown>
        {streaming ? (
          <span
            aria-hidden
            className="ml-0.5 inline-block h-4 w-[2px] animate-pulse bg-[var(--color-accent)] align-middle"
          />
        ) : null}
      </article>
    </section>
  );
}
