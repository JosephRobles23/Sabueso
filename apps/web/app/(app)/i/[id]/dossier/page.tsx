import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { createServerClient } from "@/lib/supabase/server";
import { getDemoMockState } from "@/lib/mocks";
import type { Country, EntityType, InvestigationStatus } from "@sabueso/shared-types";

import { DossierContent } from "./DossierContent";

import "./print.css";

export const revalidate = 60;

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://sabueso-skil.vercel.app";

type DossierEntity = { name: string; identifier: string | null; type: EntityType };

type DossierData = {
  id: string;
  status: InvestigationStatus;
  dossier_md: string | null;
  country: Country;
  progress_pct: number;
  started_at: string;
  finished_at: string | null;
  entity: DossierEntity | null;
  claim_count: number;
};

async function fetchDossier(id: string): Promise<DossierData | null> {
  const mock = getDemoMockState(id);
  if (mock && mock.dossier_md) {
    return {
      id: mock.id,
      status: mock.status,
      dossier_md: mock.dossier_md,
      country: "pe",
      progress_pct: mock.progress,
      started_at: mock.events[0]?.created_at ?? new Date().toISOString(),
      finished_at: mock.events[mock.events.length - 1]?.created_at ?? null,
      entity: { name: mock.target_name, identifier: null, type: "person" },
      claim_count: mock.claims.length,
    };
  }

  if (!UUID_RE.test(id)) return null;
  const supabase = await createServerClient();
  if (!supabase) return null;

  const { data, error } = await supabase
    .from("investigations")
    .select(
      "id, status, dossier_md, country, progress_pct, started_at, finished_at, entity:target_entity_id ( name, identifier, type )",
    )
    .eq("id", id)
    .eq("is_public", true)
    .maybeSingle();

  if (error || !data) return null;

  const { count } = await supabase
    .from("claims")
    .select("id", { count: "exact", head: true })
    .eq("investigation_id", id);

  const rawEntity = data.entity as DossierEntity | DossierEntity[] | null;
  const entity = Array.isArray(rawEntity) ? (rawEntity[0] ?? null) : (rawEntity ?? null);

  return {
    id: data.id as string,
    status: data.status as InvestigationStatus,
    dossier_md: (data.dossier_md as string | null) ?? null,
    country: data.country as Country,
    progress_pct: data.progress_pct as number,
    started_at: data.started_at as string,
    finished_at: (data.finished_at as string | null) ?? null,
    entity,
    claim_count: count ?? 0,
  };
}

export async function generateMetadata(
  { params }: { params: Promise<{ id: string }> },
): Promise<Metadata> {
  const { id } = await params;
  const data = await fetchDossier(id);
  const entityName = data?.entity?.name ?? "Investigación";
  const title = `${entityName} · Dossier Sabueso`;
  const description = data
    ? `Investigación pública sobre ${entityName} con ${data.claim_count} hallazgos citados, generada por la redacción de IA de Sabueso.`
    : "Investigación periodística asistida por IA. Hallazgos citados, fuentes públicas, dossier abierto.";
  const canonical = `${SITE_URL}/i/${id}/dossier`;
  const ogImage = `${SITE_URL}/api/og?id=${id}`;

  return {
    title,
    description,
    alternates: { canonical },
    openGraph: {
      type: "article",
      title,
      description,
      url: canonical,
      siteName: "Sabueso",
      locale: "es_PE",
      images: [{ url: ogImage, width: 1200, height: 630, alt: title }],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [ogImage],
    },
    robots: {
      index: data?.status === "complete",
      follow: true,
    },
  };
}

export default async function DossierPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const data = await fetchDossier(id);
  if (!data) notFound();

  const finishedIso = data.finished_at ?? data.started_at;

  return (
    <article className="dossier mx-auto w-full max-w-[760px] px-6 py-10 print:max-w-none print:px-0 print:py-0">
      <header className="dossier-header mb-8 border-b border-[var(--color-border-default)] pb-6">
        <p className="font-mono text-[11px] uppercase tracking-wider text-[var(--color-text-muted)]">
          INV-{data.id.slice(0, 8)} · {data.country.toUpperCase()}
        </p>
        <h1 className="mt-2 font-display text-4xl tracking-tight">
          {data.entity?.name ?? "Investigación"}
        </h1>
        {data.entity?.identifier ? (
          <p className="mt-1 font-mono text-xs text-[var(--color-text-secondary)]">
            {data.entity.identifier}
          </p>
        ) : null}
        <p className="mt-3 text-sm text-[var(--color-text-secondary)]">
          Dossier público generado por Sabueso · {data.claim_count} hallazgos citados ·{" "}
          <time dateTime={finishedIso}>{new Date(finishedIso).toLocaleDateString("es-PE")}</time>
        </p>
      </header>

      {data.status === "complete" && data.dossier_md ? (
        <section className="dossier-body space-y-4 text-base leading-7 text-[var(--color-text-primary)]">
          <DossierContent dossier_md={data.dossier_md} />
        </section>
      ) : (
        <DossierSkeleton status={data.status} progress={data.progress_pct} />
      )}

      <footer className="mt-12 border-t border-[var(--color-border-default)] pt-6 font-mono text-xs uppercase tracking-wider text-[var(--color-text-muted)]">
        Sabueso · hack@latam 2026 · {new Date(finishedIso).toISOString()}
      </footer>
    </article>
  );
}

function DossierSkeleton({
  status,
  progress,
}: {
  status: InvestigationStatus;
  progress: number;
}) {
  return (
    <section aria-busy="true" className="space-y-4 print:hidden">
      <p className="text-sm text-[var(--color-text-secondary)]">
        Investigación en curso ({status}) — {progress}%. Esta página se actualiza cuando la
        síntesis termina.
      </p>
      <div className="h-1 overflow-hidden rounded-full bg-[var(--color-surface-2)]">
        <div
          className="h-full bg-[var(--color-accent)] transition-[width] duration-500"
          style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
        />
      </div>
      <div className="space-y-3 pt-4">
        {Array.from({ length: 10 }).map((_, i) => (
          <div
            key={i}
            className="h-3 rounded-full bg-[var(--color-surface-2)]"
            style={{ width: `${65 + ((i * 23) % 30)}%` }}
          />
        ))}
      </div>
    </section>
  );
}
