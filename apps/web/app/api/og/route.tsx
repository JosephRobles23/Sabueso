import { ImageResponse } from "next/og";
import { NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";

// Edge runtime keeps Satori cold-start fast and avoids Node fs/font lookups.
export const runtime = "edge";

// 1h cache de la imagen rendereada y de los blobs de fuente.
export const revalidate = 3600;

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

type SatoriFont = {
  name: string;
  data: ArrayBuffer;
  weight: 400 | 500 | 600 | 700;
  style: "normal";
};

async function loadGoogleFont(family: string, weight: number): Promise<ArrayBuffer | null> {
  try {
    const cssUrl = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(family)}:wght@${weight}&display=swap`;
    const css = await fetch(cssUrl, {
      // Algunos CDNs entregan woff2 a UAs modernos; pedimos un UA típico
      // para asegurar que devuelvan un formato que Satori sabe parsear.
      headers: { "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" },
      next: { revalidate: 3600 },
    }).then((r) => (r.ok ? r.text() : ""));
    if (!css) return null;
    const match = css.match(/src:\s*url\((https:[^)]+?)\)\s*format/);
    if (!match) return null;
    const fontRes = await fetch(match[1], { next: { revalidate: 3600 } });
    if (!fontRes.ok) return null;
    return await fontRes.arrayBuffer();
  } catch {
    return null;
  }
}

export async function GET(request: Request): Promise<Response> {
  const url = new URL(request.url);
  const id = url.searchParams.get("id");

  if (!id || !UUID_RE.test(id)) {
    return NextResponse.json({ error: "Missing or invalid `id`" }, { status: 400 });
  }

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!supabaseUrl || !supabaseKey) {
    return NextResponse.json({ error: "Supabase not configured" }, { status: 500 });
  }

  const supabase = createClient(supabaseUrl, supabaseKey, {
    auth: { persistSession: false, autoRefreshToken: false },
  });

  const [investigationRes, claimsRes, displayFont, monoFont] = await Promise.all([
    supabase
      .from("investigations")
      .select("status, country, started_at, entity:target_entity_id ( name, type )")
      .eq("id", id)
      .eq("is_public", true)
      .maybeSingle(),
    supabase
      .from("claims")
      .select("confidence", { count: "exact" })
      .eq("investigation_id", id),
    loadGoogleFont("Lora", 600),
    loadGoogleFont("JetBrains Mono", 500),
  ]);

  const investigation = investigationRes.data;
  const rawEntity = investigation?.entity as
    | { name: string; type: string }
    | { name: string; type: string }[]
    | null
    | undefined;
  const entity = Array.isArray(rawEntity) ? rawEntity[0] : rawEntity;
  const entityName = entity?.name?.trim() || "Investigación";
  const claimRows = claimsRes.data ?? [];
  const claimCount = claimsRes.count ?? claimRows.length;
  const avgConfidence =
    claimRows.length > 0
      ? claimRows.reduce((sum, row) => sum + Number(row.confidence ?? 0), 0) / claimRows.length
      : 0;
  const scorePct = Math.round(avgConfidence * 100);
  const initial = entityName.charAt(0).toUpperCase() || "S";
  const country = (investigation?.country as string | undefined)?.toUpperCase() ?? "—";
  const timestamp = (investigation?.started_at as string | undefined)
    ? new Date(investigation!.started_at as string).toISOString().slice(0, 10)
    : new Date().toISOString().slice(0, 10);

  const fonts: SatoriFont[] = [];
  if (displayFont) fonts.push({ name: "Display", data: displayFont, weight: 600, style: "normal" });
  if (monoFont) fonts.push({ name: "Mono", data: monoFont, weight: 500, style: "normal" });

  // Truncate so the headline never breaks the layout at 1200x630.
  const displayName = entityName.length > 48 ? `${entityName.slice(0, 46)}…` : entityName;

  return new ImageResponse(
    (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          width: "100%",
          height: "100%",
          background: "#FAF9F5",
          padding: "56px 64px",
          fontFamily: "Display, serif",
          color: "#141413",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: 56,
                height: 56,
                borderRadius: 28,
                background: "#DA7756",
                color: "#FAF9F5",
                fontFamily: "Display, serif",
                fontSize: 30,
              }}
            >
              S
            </div>
            <span
              style={{
                display: "flex",
                fontFamily: "Mono, monospace",
                fontSize: 18,
                letterSpacing: 2,
                textTransform: "uppercase",
                color: "#5a5750",
              }}
            >
              Sabueso · Investigación pública
            </span>
          </div>
          <span
            style={{
              display: "flex",
              fontFamily: "Mono, monospace",
              fontSize: 14,
              padding: "8px 14px",
              border: "1px solid #d4d2ca",
              borderRadius: 999,
              color: "#5a5750",
              textTransform: "uppercase",
              letterSpacing: 1,
            }}
          >
            {country} · INV-{id.slice(0, 8)}
          </span>
        </div>

        <div
          style={{
            display: "flex",
            flex: 1,
            flexDirection: "row",
            alignItems: "center",
            gap: 36,
            marginTop: 40,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: 144,
              height: 144,
              borderRadius: 72,
              background: "#eeece2",
              border: "1px solid #d4d2ca",
              fontFamily: "Display, serif",
              fontSize: 76,
              color: "#141413",
              flexShrink: 0,
            }}
          >
            {initial}
          </div>
          <div style={{ display: "flex", flexDirection: "column", flex: 1 }}>
            <span
              style={{
                display: "flex",
                fontFamily: "Display, serif",
                fontSize: 60,
                lineHeight: 1.05,
                letterSpacing: -1.2,
                color: "#141413",
              }}
            >
              {displayName}
            </span>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 20,
                marginTop: 18,
              }}
            >
              <span
                style={{
                  display: "flex",
                  fontFamily: "Mono, monospace",
                  fontSize: 22,
                  color: "#141413",
                  background: "#eeece2",
                  borderRadius: 999,
                  padding: "8px 18px",
                }}
              >
                {claimCount} hallazgos
              </span>
              <span
                style={{
                  display: "flex",
                  fontFamily: "Mono, monospace",
                  fontSize: 22,
                  color: "#FAF9F5",
                  background: "#DA7756",
                  borderRadius: 999,
                  padding: "8px 18px",
                }}
              >
                {scorePct}% confianza
              </span>
            </div>
          </div>
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            borderTop: "1px solid #d4d2ca",
            paddingTop: 18,
            marginTop: 24,
          }}
        >
          <span
            style={{
              display: "flex",
              fontFamily: "Mono, monospace",
              fontSize: 16,
              color: "#5a5750",
              textTransform: "uppercase",
              letterSpacing: 1,
            }}
          >
            sabueso-skil.vercel.app
          </span>
          <span
            style={{
              display: "flex",
              fontFamily: "Mono, monospace",
              fontSize: 16,
              color: "#5a5750",
            }}
          >
            {timestamp}
          </span>
        </div>
      </div>
    ),
    {
      width: 1200,
      height: 630,
      ...(fonts.length > 0 ? { fonts } : {}),
    },
  );
}
