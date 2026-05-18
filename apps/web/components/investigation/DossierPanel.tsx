"use client";

import * as React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { cn } from "@/lib/utils";

import { ConfidenceBadge } from "./ConfidenceBadge";
import { EvidenceChip, type EvidenceSourceType } from "./EvidenceChip";
import { MermaidDiagram } from "./MermaidDiagram";

export interface DossierPanelProps {
  dossier_md: string;
  streaming?: boolean;
  className?: string;
}

const CONF_TAG_RE = /<conf\s+v="([\d.]+)"\s*\/>/g;
const SRC_TAG_RE = /<src\s+url="([^"]+)"(?:\s+type="([^"]+)")?\s*\/>/g;

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

function PreBlock({ children }: React.HTMLAttributes<HTMLPreElement> & { children?: React.ReactNode }) {
  const child = React.Children.toArray(children)[0];
  if (React.isValidElement(child)) {
    const props = child.props as { className?: string; children?: React.ReactNode };
    const match = /language-(\w+)/.exec(props.className || "");
    if (match?.[1] === "mermaid") {
      const code = String(props.children).replace(/\n$/, "");
      return <MermaidDiagram chart={code} className="my-4" />;
    }
  }
  return (
    <pre className="my-4 overflow-x-auto rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-2)] p-4 font-mono text-xs leading-relaxed text-[var(--color-text-primary)]">
      {children}
    </pre>
  );
}

function InlineCode({ children, ...props }: React.HTMLAttributes<HTMLElement>) {
  return (
    <code
      className="rounded bg-[var(--color-surface-2)] px-1.5 py-0.5 font-mono text-[0.85em] text-[var(--color-text-primary)]"
      {...props}
    >
      {children}
    </code>
  );
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
          "dossier-content min-h-0 flex-1 overflow-y-auto px-5 py-4",
          "text-sm leading-relaxed text-[var(--color-text-primary)]",
        )}
      >
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            h1: ({ children }) => (
              <h1 className="mb-4 mt-6 font-display text-2xl tracking-tight text-[var(--color-text-primary)] first:mt-0">
                {substitute(children)}
              </h1>
            ),
            h2: ({ children }) => (
              <h2 className="mb-3 mt-8 border-b border-[var(--color-border-default)] pb-2 font-display text-xl tracking-tight text-[var(--color-text-primary)]">
                {substitute(children)}
              </h2>
            ),
            h3: ({ children }) => (
              <h3 className="mb-2 mt-6 font-display text-lg tracking-tight text-[var(--color-text-primary)]">
                {substitute(children)}
              </h3>
            ),
            h4: ({ children }) => (
              <h4 className="mb-2 mt-4 font-display text-base font-semibold text-[var(--color-text-primary)]">
                {substitute(children)}
              </h4>
            ),
            p: ({ children }) => (
              <p className="my-3 leading-relaxed text-[var(--color-text-primary)]">
                {substitute(children)}
              </p>
            ),
            blockquote: ({ children }) => (
              <blockquote className="my-4 border-l-2 border-[var(--color-accent)] bg-[var(--color-surface-2)]/50 py-2 pl-4 pr-3 text-[var(--color-text-secondary)] italic">
                {substitute(children)}
              </blockquote>
            ),
            ul: ({ children }) => (
              <ul className="my-3 list-disc space-y-1.5 pl-6 marker:text-[var(--color-text-muted)]">
                {children}
              </ul>
            ),
            ol: ({ children }) => (
              <ol className="my-3 list-decimal space-y-1.5 pl-6 marker:text-[var(--color-text-muted)]">
                {children}
              </ol>
            ),
            li: ({ children }) => (
              <li className="text-[var(--color-text-primary)]">
                {substitute(children)}
              </li>
            ),
            strong: ({ children }) => (
              <strong className="font-semibold text-[var(--color-text-primary)]">{children}</strong>
            ),
            a: ({ href, children }) => (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[var(--color-accent)] underline decoration-[var(--color-accent)]/30 underline-offset-2 hover:decoration-[var(--color-accent)]"
              >
                {children}
              </a>
            ),
            hr: () => (
              <hr className="my-6 border-[var(--color-border-default)]" />
            ),
            table: ({ children }) => (
              <div className="my-4 overflow-x-auto rounded-lg border border-[var(--color-border-default)]">
                <table className="w-full border-collapse text-xs">
                  {children}
                </table>
              </div>
            ),
            thead: ({ children }) => (
              <thead className="bg-[var(--color-surface-2)]">
                {children}
              </thead>
            ),
            th: ({ children }) => (
              <th className="border-b border-[var(--color-border-default)] px-3 py-2 text-left font-mono text-[10px] font-semibold uppercase tracking-wider text-[var(--color-text-secondary)]">
                {children}
              </th>
            ),
            td: ({ children }) => (
              <td className="border-b border-[var(--color-border-default)]/50 px-3 py-2 text-[var(--color-text-primary)]">
                {substitute(children)}
              </td>
            ),
            tr: ({ children }) => (
              <tr className="transition-colors hover:bg-[var(--color-surface-2)]/50">
                {children}
              </tr>
            ),
            pre: PreBlock,
            code: InlineCode,
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
