"use client";

/**
 * SankeyView — Investigation Floor "Flujo de dinero" mode.
 *
 * Renders @nivo/sankey over the subset of `edges` that represent money flows
 * (type matches MONEY_FLOW_TYPES, or any edge with `metadata.amount_pen`).
 * Link color is green when the recipient is declared / arms-length and red
 * when the edge points to a close beneficiary (`metadata.is_relative === true`
 * or semantic ∈ {suspicious, conflict}). Empty dataset → Spanish empty state.
 */

import * as React from "react";
import { ResponsiveSankey } from "@nivo/sankey";

import type { GraphEdge, GraphEntity } from "@/lib/mockInvestigationState";
import { cn } from "@/lib/utils";

const MONEY_FLOW_TYPES = new Set([
  "received_amount",
  "pago",
  "transferencia",
  "adjudicataria",
]);

const COLOR_DECLARED = "#788C5D"; // verde — declarado / arms-length
const COLOR_RELATIVE = "#C4583A"; // rojo — beneficiario cercano

export interface SankeyViewProps {
  entities: GraphEntity[];
  edges: GraphEdge[];
  className?: string;
}

type SankeyNode = {
  id: string;
  nodeColor: string;
};

type SankeyLink = {
  source: string;
  target: string;
  value: number;
  startColor: string;
  endColor: string;
  /** raw amount in PEN, for tooltip formatting. */
  amount: number;
  isRelative: boolean;
};

const PEN_FORMATTER = new Intl.NumberFormat("es-PE", {
  style: "currency",
  currency: "PEN",
  maximumFractionDigits: 0,
});

export function SankeyView({ entities, edges, className }: SankeyViewProps) {
  const { nodes, links, totalAmount } = React.useMemo(
    () => buildSankeyData(entities, edges),
    [entities, edges],
  );

  if (links.length === 0) {
    return (
      <section
        aria-label="Flujo de dinero"
        className={cn(
          "relative flex h-full min-h-0 flex-col overflow-hidden rounded-[var(--radius-lg)] border bg-[var(--color-canvas)]",
          className,
        )}
      >
        <header className="flex items-center justify-between border-b border-[var(--color-border-default)] bg-[var(--color-surface)] px-4 py-3">
          <h2 className="font-display text-lg">Flujo de dinero</h2>
          <span className="font-mono text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
            0 flujos
          </span>
        </header>
        <div className="flex flex-1 items-center justify-center px-6 text-center">
          <p className="max-w-sm text-sm text-[var(--color-text-muted)]">
            Sin datos de flujos de dinero aún.
            <br />
            <span className="font-mono text-[10px] uppercase tracking-wider">
              El contador está cruzando SEACE
            </span>
          </p>
        </div>
      </section>
    );
  }

  return (
    <section
      aria-label="Flujo de dinero"
      className={cn(
        "relative flex h-full min-h-0 flex-col overflow-hidden rounded-[var(--radius-lg)] border bg-[var(--color-canvas)]",
        className,
      )}
    >
      <header className="flex items-center justify-between border-b border-[var(--color-border-default)] bg-[var(--color-surface)] px-4 py-3">
        <h2 className="font-display text-lg">Flujo de dinero</h2>
        <span className="font-mono text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
          {links.length} flujos · {PEN_FORMATTER.format(totalAmount)}
        </span>
      </header>

      <div className="relative min-h-0 flex-1">
        <ResponsiveSankey
          data={{ nodes, links }}
          margin={{ top: 16, right: 140, bottom: 16, left: 24 }}
          align="justify"
          colors={(n) => (n as SankeyNode).nodeColor ?? "#94A3B8"}
          nodeOpacity={1}
          nodeHoverOthersOpacity={0.35}
          nodeThickness={14}
          nodeSpacing={18}
          nodeBorderWidth={0}
          nodeBorderRadius={2}
          linkOpacity={0.55}
          linkHoverOthersOpacity={0.12}
          linkContract={2}
          enableLinkGradient={true}
          labelPosition="outside"
          labelOrientation="horizontal"
          labelPadding={10}
          labelTextColor={{ from: "color", modifiers: [["darker", 1.6]] }}
          theme={{
            background: "transparent",
            text: {
              fontFamily:
                'var(--font-mono, "JetBrains Mono"), ui-monospace, SFMono-Regular, monospace',
              fontSize: 11,
              fill: "var(--color-text-secondary)",
            },
            tooltip: {
              container: {
                background: "var(--color-surface)",
                color: "var(--color-text-primary)",
                fontSize: 12,
                borderRadius: 8,
                border: "1px solid var(--color-border-default)",
                padding: "8px 10px",
                boxShadow: "0 8px 24px rgba(0,0,0,0.18)",
              },
            },
          }}
          linkTooltip={({ link }) => {
            const raw = link as unknown as {
              amount: number;
              isRelative: boolean;
              source: { id: string };
              target: { id: string };
            };
            return (
              <div className="font-mono text-xs">
                <div className="font-display text-sm">
                  {raw.source.id} → {raw.target.id}
                </div>
                <div className="mt-1 tabular-nums text-[var(--color-text-primary)]">
                  {PEN_FORMATTER.format(raw.amount)}
                </div>
                <div
                  className="mt-1 text-[10px] uppercase tracking-wider"
                  style={{ color: raw.isRelative ? COLOR_RELATIVE : COLOR_DECLARED }}
                >
                  {raw.isRelative ? "Beneficiario cercano" : "Declarado"}
                </div>
              </div>
            );
          }}
          nodeTooltip={({ node }) => (
            <div className="font-mono text-xs">
              <div className="font-display text-sm">{node.id}</div>
              <div className="mt-1 tabular-nums text-[var(--color-text-primary)]">
                {PEN_FORMATTER.format(node.value)}
              </div>
            </div>
          )}
          ariaLabel="Diagrama de flujo de dinero"
        />

        <ul
          aria-hidden
          className="pointer-events-none absolute bottom-2 left-2 flex flex-wrap gap-1.5 text-[10px]"
        >
          <li
            className="inline-flex items-center gap-1 rounded-full bg-[var(--color-surface)]/85 px-2 py-0.5 font-mono backdrop-blur"
            style={{ color: COLOR_DECLARED }}
          >
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{ backgroundColor: COLOR_DECLARED }}
            />
            Declarado
          </li>
          <li
            className="inline-flex items-center gap-1 rounded-full bg-[var(--color-surface)]/85 px-2 py-0.5 font-mono backdrop-blur"
            style={{ color: COLOR_RELATIVE }}
          >
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{ backgroundColor: COLOR_RELATIVE }}
            />
            Beneficiario cercano
          </li>
        </ul>
      </div>
    </section>
  );
}

function isMoneyFlow(edge: GraphEdge): boolean {
  if (MONEY_FLOW_TYPES.has(edge.type)) return true;
  const amount = edge.metadata?.amount_pen;
  return typeof amount === "number" && amount > 0;
}

function buildSankeyData(
  entities: GraphEntity[],
  edges: GraphEdge[],
): { nodes: SankeyNode[]; links: SankeyLink[]; totalAmount: number } {
  const moneyEdges = edges.filter(isMoneyFlow);
  if (moneyEdges.length === 0) {
    return { nodes: [], links: [], totalAmount: 0 };
  }

  const nameById = new Map<string, string>(entities.map((e) => [e.id, e.name]));
  const usedIds = new Set<string>();
  let totalAmount = 0;

  // Aggregate parallel edges (same source/target) so the diagram doesn't end up
  // with duplicate strands. The aggregated edge inherits the "redder" semantics
  // (any leg with is_relative or suspicious/conflict makes the whole aggregate
  // red — bad-apple wins).
  const grouped = new Map<
    string,
    { source: string; target: string; amount: number; isRelative: boolean }
  >();

  for (const e of moneyEdges) {
    const amount =
      typeof e.metadata?.amount_pen === "number"
        ? (e.metadata.amount_pen as number)
        : Math.max(1, e.weight) * 1_000_000;

    const isRelative =
      e.metadata?.is_relative === true ||
      e.semantic === "suspicious" ||
      e.semantic === "conflict";

    const fromName = nameById.get(e.from) ?? e.from;
    const toName = nameById.get(e.to) ?? e.to;
    if (fromName === toName) continue;

    const key = `${fromName}→${toName}`;
    const existing = grouped.get(key);
    if (existing) {
      existing.amount += amount;
      existing.isRelative = existing.isRelative || isRelative;
    } else {
      grouped.set(key, { source: fromName, target: toName, amount, isRelative });
    }
    usedIds.add(fromName);
    usedIds.add(toName);
    totalAmount += amount;
  }

  const links: SankeyLink[] = [];
  for (const g of grouped.values()) {
    const color = g.isRelative ? COLOR_RELATIVE : COLOR_DECLARED;
    links.push({
      source: g.source,
      target: g.target,
      value: Math.max(1, g.amount),
      startColor: color,
      endColor: color,
      amount: g.amount,
      isRelative: g.isRelative,
    });
  }

  const nodes: SankeyNode[] = Array.from(usedIds).map((id) => {
    // Node color = the "reddest" outgoing edge from this node, so a source that
    // pays out to a relative reads as the suspicious end.
    const outgoingRed = links.some((l) => l.source === id && l.isRelative);
    return {
      id,
      nodeColor: outgoingRed ? COLOR_RELATIVE : COLOR_DECLARED,
    };
  });

  return { nodes, links, totalAmount };
}
