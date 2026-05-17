import type { InvestigatorCallsign, AgentStatus } from "@sabueso/shared-types";
import { INVESTIGATORS } from "@sabueso/shared-types";

import {
  ConfidenceBadge,
  DelegationArrow,
  EvidenceChip,
  InvestigatorAvatar,
  InvestigatorWorkstation,
  StatusPill,
  type EvidenceSourceType,
} from "@/components/investigation";

export const dynamic = "force-static";

const ALL_STATUSES: AgentStatus[] = ["idle", "thinking", "working", "blocked", "done"];

const WORKSTATION_MOCK: Array<{
  callsign: InvestigatorCallsign;
  status: AgentStatus;
  detail?: string;
  speechText?: string;
}> = [
  { callsign: "sabueso", status: "thinking", speechText: "Planificando cruces JNE/SEACE…" },
  { callsign: "el-buscador", status: "done", detail: "RUC 20100070970" },
  { callsign: "la-tasadora", status: "working", detail: "Querying SUNARP" },
  { callsign: "el-contador", status: "working", detail: "4 contratos S/.10M", speechText: "Cruzando 4 fuentes…" },
  { callsign: "el-letrado", status: "idle" },
  { callsign: "el-detective", status: "blocked", detail: "403 en SUNARP-board" },
  { callsign: "el-periodista", status: "idle" },
  { callsign: "la-jueza", status: "thinking", speechText: "Verificando claim 0xA1B2…" },
];

const EVIDENCE_MOCK: Array<{ type: EvidenceSourceType; url: string; label?: string }> = [
  { type: "jne", url: "https://plataformaelectoral.jne.gob.pe/Candidato/Declaracion/12345" },
  { type: "seace", url: "https://prodapp2.seace.gob.pe/seacebus-uiwd/consulta/12345" },
  { type: "sunarp", url: "https://www.sunarp.gob.pe/registros/predios/lima/01234" },
  { type: "news", url: "https://elcomercio.pe/politica/cerron-investigado-2024" },
  { type: "legalize", url: "https://legalize.pe/normas/ley-31234" },
  { type: "other", url: "https://datosabiertos.gob.pe/dataset/contratos-2024", label: "Open Data" },
];

const CONFIDENCE_SAMPLES = [0.42, 0.61, 0.72, 0.86, 0.94, 0.99];

const ARROW_LAYOUT: Array<{
  from: InvestigatorCallsign;
  to: InvestigatorCallsign;
  status: "running" | "done" | "blocked";
  fromX: number;
  toX: number;
}> = [
  { from: "sabueso", to: "el-buscador", status: "done", fromX: 60, toX: 180 },
  { from: "sabueso", to: "la-tasadora", status: "running", fromX: 60, toX: 300 },
  { from: "sabueso", to: "el-contador", status: "running", fromX: 60, toX: 420 },
  { from: "el-contador", to: "el-detective", status: "blocked", fromX: 420, toX: 540 },
];

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="border-b border-[var(--color-border-default)] pb-12">
      <header className="mb-6">
        <h2 className="font-display text-2xl text-[var(--color-text-primary)]">{title}</h2>
        {subtitle ? (
          <p className="mt-1 text-sm text-[var(--color-text-secondary)]">{subtitle}</p>
        ) : null}
      </header>
      {children}
    </section>
  );
}

function Tile({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-[var(--radius-md)] border bg-[var(--color-surface)] p-4">
      <div className="flex min-h-[140px] items-center justify-center">{children}</div>
      <span className="font-mono text-[10px] text-[var(--color-text-muted)] uppercase tracking-wide">
        {label}
      </span>
    </div>
  );
}

export default function DevComponentsPage() {
  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <header className="mb-10">
        <p className="font-mono text-[11px] text-[var(--color-text-muted)] uppercase tracking-widest">
          S-12 · Componentes atómicos
        </p>
        <h1 className="mt-1 font-display text-4xl text-[var(--color-text-primary)]">
          Sabueso · Component Gallery
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--color-text-secondary)]">
          Aislamiento visual de los 6 componentes atómicos. Mock data hardcoded — los datos reales
          (SSE/Realtime) se enchufan en pasos posteriores de S-12.
        </p>
      </header>

      <div className="flex flex-col gap-12">
        {/* ──────────────────────────────── StatusPill ─────────────────────────────── */}
        <Section
          title="StatusPill"
          subtitle="5 estados: idle · thinking · working · blocked · done. Acepta `detail` truncado a 28 chars."
        >
          <div className="flex flex-wrap items-center gap-3">
            {ALL_STATUSES.map((s) => (
              <StatusPill key={s} status={s} />
            ))}
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <StatusPill status="working" detail="Trazando flujos SEACE 2014-2018" />
            <StatusPill status="blocked" detail="search_sunarp · 403 Forbidden" />
            <StatusPill status="done" detail="✓ 0.94" />
            <StatusPill status="thinking" size="md" />
          </div>
        </Section>

        {/* ─────────────────────────────── ConfidenceBadge ─────────────────────────── */}
        <Section
          title="ConfidenceBadge"
          subtitle="Acepta value ∈ [0,1] (matches Claim.confidence); muestra 0-100. Umbrales: ≥85 verde · ≥60 ámbar · resto rojo."
        >
          <div className="flex flex-wrap items-center gap-3">
            {CONFIDENCE_SAMPLES.map((v) => (
              <ConfidenceBadge key={v} value={v} />
            ))}
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            {CONFIDENCE_SAMPLES.map((v) => (
              <ConfidenceBadge key={`md-${v}`} value={v} size="md" />
            ))}
            <ConfidenceBadge value={0.91} withGlyph={false} />
          </div>
        </Section>

        {/* ─────────────────────────────── EvidenceChip ────────────────────────────── */}
        <Section
          title="EvidenceChip"
          subtitle="Link a fuente con favicon (Google s2). Tipos: jne · seace · sunarp · news · legalize · other."
        >
          <div className="flex flex-wrap items-center gap-3">
            {EVIDENCE_MOCK.map((e) => (
              <EvidenceChip key={e.url} sourceType={e.type} sourceUrl={e.url} label={e.label} />
            ))}
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            {EVIDENCE_MOCK.slice(0, 3).map((e) => (
              <EvidenceChip key={`md-${e.url}`} sourceType={e.type} sourceUrl={e.url} size="md" />
            ))}
          </div>
        </Section>

        {/* ─────────────────────────────── InvestigatorAvatar ──────────────────────── */}
        <Section
          title="InvestigatorAvatar"
          subtitle="Notionists (Dicebear API) con seed = callsign. Tamaños 48/64/96, estados normal/active/error, speech bubble opcional."
        >
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <Tile label="48 · normal">
              <InvestigatorAvatar callsign="el-contador" size={48} />
            </Tile>
            <Tile label="64 · active">
              <InvestigatorAvatar callsign="la-tasadora" size={64} state="active" />
            </Tile>
            <Tile label="96 · error">
              <InvestigatorAvatar callsign="el-detective" size={96} state="error" />
            </Tile>
            <Tile label="speech bubble">
              <InvestigatorAvatar
                callsign="sabueso"
                size={64}
                state="active"
                withSpeechBubble
                speechText="Cruzando 4 fuentes en paralelo…"
              />
            </Tile>
          </div>

          <div className="mt-6">
            <p className="mb-3 font-mono text-[11px] uppercase text-[var(--color-text-muted)]">
              Roster completo (size 64, seed determinista por callsign)
            </p>
            <div className="grid grid-cols-4 gap-4 md:grid-cols-8">
              {INVESTIGATORS.map((inv) => (
                <Tile key={inv.callsign} label={inv.displayName}>
                  <InvestigatorAvatar callsign={inv.callsign} size={64} />
                </Tile>
              ))}
            </div>
          </div>
        </Section>

        {/* ─────────────────────────────── InvestigatorWorkstation ─────────────────── */}
        <Section
          title="InvestigatorWorkstation"
          subtitle="Disco tinted + avatar + LED pulsante (animate-pulse-led 1.4s) + placard + status pill. Click → drill-down (mock)."
        >
          <div className="rounded-[var(--radius-lg)] border bg-[var(--color-surface-2)] p-6">
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-8">
              {WORKSTATION_MOCK.map((w) => (
                <InvestigatorWorkstation
                  key={w.callsign}
                  callsign={w.callsign}
                  status={w.status}
                  detail={w.detail}
                  speechText={w.speechText}
                />
              ))}
            </div>
          </div>
        </Section>

        {/* ─────────────────────────────── DelegationArrow ─────────────────────────── */}
        <Section
          title="DelegationArrow"
          subtitle="SVG <g> (Bezier cuadrático + marching ants). Color = color del delegador. Estados: running · done · blocked."
        >
          <div className="relative overflow-hidden rounded-[var(--radius-lg)] border bg-[var(--color-surface)] p-4">
            <svg viewBox="0 0 600 200" className="h-[200px] w-full">
              {/* Anchor dots at each station position */}
              {ARROW_LAYOUT.flatMap((a, i) => [
                <circle key={`from-${i}`} cx={a.fromX} cy={160} r={4} fill="var(--color-text-muted)" />,
                <circle key={`to-${i}`} cx={a.toX} cy={160} r={4} fill="var(--color-text-muted)" />,
              ])}

              {ARROW_LAYOUT.map((a, i) => (
                <DelegationArrow
                  key={i}
                  from={{ x: a.fromX, y: 160 }}
                  to={{ x: a.toX, y: 160 }}
                  status={a.status}
                  fromCallsign={a.from}
                  arc={70}
                />
              ))}

              {/* Labels under each anchor */}
              {Array.from(new Set(ARROW_LAYOUT.flatMap((a) => [a.fromX, a.toX]))).map((x) => {
                const cs = ARROW_LAYOUT.find((a) => a.fromX === x)?.from ??
                  ARROW_LAYOUT.find((a) => a.toX === x)?.to;
                return (
                  <text
                    key={x}
                    x={x}
                    y={185}
                    textAnchor="middle"
                    className="fill-[var(--color-text-muted)] font-mono text-[10px]"
                  >
                    {cs}
                  </text>
                );
              })}
            </svg>
            <div className="mt-3 flex flex-wrap items-center gap-4 px-2 font-mono text-[11px] text-[var(--color-text-secondary)]">
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-6 rounded bg-[color:var(--color-text-secondary)]" /> running
                (marching ants)
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-6 rounded bg-[color:var(--color-text-secondary)] opacity-40" />
                done (40% opacity, sin dash)
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-6 rounded bg-[var(--color-suspicious)] animate-pulse" />
                blocked (pulse rojo)
              </span>
            </div>
          </div>
        </Section>
      </div>
    </main>
  );
}
