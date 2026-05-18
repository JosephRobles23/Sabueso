"use client"

import * as React from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

import { MermaidDiagram } from "@/components/investigation/MermaidDiagram"

export interface DossierContentProps {
  dossier_md: string
}

function PreBlock({
  children,
}: React.HTMLAttributes<HTMLPreElement> & { children?: React.ReactNode }) {
  const child = React.Children.toArray(children)[0]
  if (React.isValidElement(child)) {
    const props = child.props as { className?: string; children?: React.ReactNode }
    const match = /language-(\w+)/.exec(props.className || "")
    if (match?.[1] === "mermaid") {
      const code = String(props.children).replace(/\n$/, "")
      return <MermaidDiagram chart={code} className="my-4" />
    }
  }
  return (
    <pre className="my-4 overflow-x-auto rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-2)] p-4 font-mono text-xs leading-relaxed text-[var(--color-text-primary)]">
      {children}
    </pre>
  )
}

export function DossierContent({ dossier_md }: DossierContentProps) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        h2: ({ children }) => (
          <h2 className="mt-10 font-display text-2xl tracking-tight">{children}</h2>
        ),
        h3: ({ children }) => (
          <h3 className="mt-6 font-display text-xl tracking-tight">{children}</h3>
        ),
        p: ({ children }) => <p className="my-3">{children}</p>,
        blockquote: ({ children }) => (
          <blockquote className="border-l-2 border-[var(--color-border-strong)] pl-4 italic">
            {children}
          </blockquote>
        ),
        ul: ({ children }) => <ul className="list-disc pl-6">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal pl-6">{children}</ol>,
        li: ({ children }) => <li className="my-1">{children}</li>,
        a: ({ href, children }) => (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[var(--color-accent)] underline"
          >
            {children}
          </a>
        ),
        table: ({ children }) => (
          <div className="my-4 overflow-x-auto">
            <table className="w-full border-collapse">{children}</table>
          </div>
        ),
        th: ({ children }) => (
          <th className="border border-[var(--color-border-default)] p-2 text-left">
            {children}
          </th>
        ),
        td: ({ children }) => (
          <td className="border border-[var(--color-border-default)] p-2">{children}</td>
        ),
        code: ({ children, ...props }) => (
          <code
            className="rounded bg-[var(--color-surface-2)] px-1 py-0.5 font-mono text-sm"
            {...props}
          >
            {children}
          </code>
        ),
        pre: PreBlock,
      }}
    >
      {dossier_md}
    </ReactMarkdown>
  )
}
