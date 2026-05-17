import * as React from "react";
import type { InvestigatorCallsign } from "@sabueso/shared-types";

import { cn } from "@/lib/utils";

import { callsignColor } from "./_meta";

export type DelegationStatus = "running" | "done" | "blocked";

export interface Point {
  x: number;
  y: number;
}

export interface DelegationArrowProps
  extends Omit<React.SVGAttributes<SVGGElement>, "from" | "to" | "color"> {
  from: Point;
  to: Point;
  status: DelegationStatus;
  /** Color is the *delegator* color (spec §6.5). Falls back to fromCallsign lookup. */
  fromCallsign?: InvestigatorCallsign;
  /** Explicit color override (wins over fromCallsign). */
  color?: string;
  /** Curve height in px — positive bows the arc upward. Default 40. */
  arc?: number;
  strokeWidth?: number;
}

/**
 * Renders as an SVG <g> — must be placed inside a parent <svg> with a
 * coordinate space matching the `from`/`to` points. Uses a quadratic Bezier
 * that bows upward by `arc` pixels.
 */
export const DelegationArrow = React.forwardRef<SVGGElement, DelegationArrowProps>(
  (
    {
      from,
      to,
      status,
      fromCallsign,
      color,
      arc = 40,
      strokeWidth = 2,
      className,
      ...rest
    },
    ref,
  ) => {
    const resolvedColor =
      color ?? (fromCallsign ? callsignColor(fromCallsign) : "var(--color-accent)");

    const midX = (from.x + to.x) / 2;
    const midY = Math.min(from.y, to.y) - arc;
    const path = `M ${from.x} ${from.y} Q ${midX} ${midY} ${to.x} ${to.y}`;

    const opacity = status === "done" ? 0.4 : 1;
    const dashAnim =
      status === "running"
        ? "animate-marching-ants"
        : status === "blocked"
          ? "animate-pulse"
          : "";

    const finalColor = status === "blocked" ? "var(--color-suspicious)" : resolvedColor;

    return (
      <g
        ref={ref}
        className={cn(dashAnim, className)}
        opacity={opacity}
        aria-hidden="true"
        {...rest}
      >
        <path
          d={path}
          fill="none"
          stroke={finalColor}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={status === "done" ? undefined : "5 3"}
        />
        {/* Arrowhead at the destination, oriented along the curve tangent. */}
        <ArrowHead at={to} from={{ x: midX, y: midY }} color={finalColor} />
      </g>
    );
  },
);
DelegationArrow.displayName = "DelegationArrow";

function ArrowHead({ at, from, color }: { at: Point; from: Point; color: string }) {
  const angle = Math.atan2(at.y - from.y, at.x - from.x);
  const size = 6;
  const a1x = at.x - size * Math.cos(angle - Math.PI / 6);
  const a1y = at.y - size * Math.sin(angle - Math.PI / 6);
  const a2x = at.x - size * Math.cos(angle + Math.PI / 6);
  const a2y = at.y - size * Math.sin(angle + Math.PI / 6);
  return (
    <polygon
      points={`${at.x},${at.y} ${a1x},${a1y} ${a2x},${a2y}`}
      fill={color}
    />
  );
}
