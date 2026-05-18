"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export interface MermaidDiagramProps {
  chart: string;
  className?: string;
}

export function MermaidDiagram({ chart, className }: MermaidDiagramProps) {
  const containerRef = React.useRef<HTMLDivElement>(null);
  const [svg, setSvg] = React.useState<string>("");
  const [error, setError] = React.useState<string | null>(null);
  const idRef = React.useRef(`mermaid-${Math.random().toString(36).slice(2, 9)}`);

  React.useEffect(() => {
    let cancelled = false;

    async function render() {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({
          startOnLoad: false,
          theme: "dark",
          themeVariables: {
            primaryColor: "#DA7756",
            primaryTextColor: "#FAF9F5",
            primaryBorderColor: "#DA775680",
            lineColor: "#6A9BCC",
            secondaryColor: "#1e1e1d",
            tertiaryColor: "#1e1e1d",
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
            fontSize: "12px",
            nodeBorder: "1px",
            mainBkg: "#1e1e1d",
            clusterBkg: "#1e1e1d",
          },
          flowchart: {
            htmlLabels: true,
            curve: "basis",
            padding: 12,
            nodeSpacing: 40,
            rankSpacing: 50,
          },
          securityLevel: "loose",
        });

        const { svg: result } = await mermaid.render(idRef.current, chart.trim());
        if (!cancelled) {
          setSvg(result);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Error al renderizar diagrama");
        }
      }
    }

    render();
    return () => { cancelled = true; };
  }, [chart]);

  if (error) {
    return (
      <div className={cn("overflow-x-auto rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-2)] p-4", className)}>
        <pre className="font-mono text-xs text-[var(--color-text-muted)] whitespace-pre-wrap">{chart}</pre>
      </div>
    );
  }

  if (!svg) {
    return (
      <div className={cn("flex items-center justify-center rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-2)] p-8", className)}>
        <span className="font-mono text-xs text-[var(--color-text-muted)]">Renderizando diagrama…</span>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={cn(
        "overflow-x-auto rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-2)]/50 p-4",
        "[&_svg]:mx-auto [&_svg]:max-w-full",
        className,
      )}
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
