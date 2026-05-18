#!/usr/bin/env -S node --experimental-strip-types
/**
 * scripts/record-demos.ts — pre-cache de los 5 demos del pitch (S-17).
 *
 * Lanza un POST /api/v1/investigations por cada DEMO_TARGET, dren a el SSE
 * hasta status=complete (con timeout duro de 5min/demo), valida que cada
 * investigación tenga ≥1 claim_created event antes de aceptarla, y al
 * terminar imprime un patch para `apps/web/lib/demos.ts` con los UUIDs.
 *
 * Uso (recomendado):
 *   API_BASE=http://localhost:8000 \
 *   pnpm tsx scripts/record-demos.ts
 *
 * Variables:
 *   API_BASE              default http://localhost:8000
 *   API_PREFIX            default /api/v1
 *   API_TOKEN             opcional, Bearer si está set
 *   DEMO_TIMEOUT_MS       default 300000 (5min/demo)
 *   ONLY                  CSV de slugs a correr (ej: keiko-fujimori,minsa)
 *
 * Salida:
 *   - stdout: log estructurado por demo (slug, started_at, id, status)
 *   - al final: snippet TS listo para reemplazar el array DEMO_TARGETS
 *
 * No actualiza la DB ni el seed; eso lo hace
 * `scripts/dump-demo-investigations.sh` después de validar editorialmente.
 */
import { DEMO_TARGETS, type DemoTarget } from "../apps/web/lib/demos.ts";

const API_BASE = process.env.API_BASE ?? "http://localhost:8000";
const API_PREFIX = process.env.API_PREFIX ?? "/api/v1";
const API_TOKEN = process.env.API_TOKEN ?? "";
const TIMEOUT_MS = Number(process.env.DEMO_TIMEOUT_MS ?? 300_000);
const ONLY = (process.env.ONLY ?? "")
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);

interface PreCacheResult {
  slug: string;
  ok: boolean;
  investigation_id: string;
  claim_count: number;
  duration_ms: number;
  reason?: string;
}

function authHeaders(): Record<string, string> {
  return API_TOKEN ? { Authorization: `Bearer ${API_TOKEN}` } : {};
}

async function postInvestigate(target: DemoTarget): Promise<string> {
  const res = await fetch(`${API_BASE}${API_PREFIX}/investigations`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ target_query: target.name, country: target.country }),
  });
  if (!res.ok) {
    throw new Error(`POST /investigations failed: ${res.status} ${await res.text()}`);
  }
  const data = (await res.json()) as { id: string };
  if (!data?.id) throw new Error("API response missing 'id'");
  return data.id;
}

async function drainSse(id: string, timeoutMs: number): Promise<{ claims: number; ok: boolean }> {
  // Node 20+ tiene EventSource via undici, pero para ser conservador usamos
  // fetch streaming directamente: parsemos texto y contamos eventos.
  const url = `${API_BASE}${API_PREFIX}/investigations/${id}/events`;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);

  const res = await fetch(url, { headers: { Accept: "text/event-stream", ...authHeaders() }, signal: ctrl.signal });
  if (!res.body) throw new Error("SSE response has no body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let claims = 0;
  let terminal: "complete" | "failed" | null = null;

  try {
    while (!terminal) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      // SSE chunks: split por doble newline
      let idx: number;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        const chunk = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        // extraer payload de líneas data: ...
        const dataLine = chunk
          .split("\n")
          .find((l) => l.startsWith("data:"));
        if (!dataLine) continue;
        try {
          const evt = JSON.parse(dataLine.slice(5).trim()) as { type?: string };
          if (evt.type === "claim_created") claims += 1;
          if (evt.type === "investigation_complete") terminal = "complete";
          if (evt.type === "investigation_failed") terminal = "failed";
        } catch {
          /* keep parsing */
        }
      }
    }
  } finally {
    clearTimeout(timer);
    try {
      reader.cancel();
    } catch {
      /* noop */
    }
  }

  return { claims, ok: terminal === "complete" };
}

async function runOne(target: DemoTarget): Promise<PreCacheResult> {
  const t0 = Date.now();
  try {
    const id = await postInvestigate(target);
    process.stdout.write(`  · ${target.slug} → investigation_id=${id}\n`);
    const { claims, ok } = await drainSse(id, TIMEOUT_MS);
    const ms = Date.now() - t0;
    if (!ok) {
      return { slug: target.slug, ok: false, investigation_id: id, claim_count: claims, duration_ms: ms, reason: "did not reach status=complete" };
    }
    if (claims < 1) {
      return { slug: target.slug, ok: false, investigation_id: id, claim_count: claims, duration_ms: ms, reason: "0 claim_created events — investigar antes de aceptar" };
    }
    return { slug: target.slug, ok: true, investigation_id: id, claim_count: claims, duration_ms: ms };
  } catch (err) {
    return {
      slug: target.slug,
      ok: false,
      investigation_id: "",
      claim_count: 0,
      duration_ms: Date.now() - t0,
      reason: err instanceof Error ? err.message : String(err),
    };
  }
}

function printPatch(results: PreCacheResult[]): void {
  process.stdout.write(`\n──── Patch para apps/web/lib/demos.ts ────\n`);
  for (const r of results) {
    if (!r.ok) continue;
    process.stdout.write(
      `  ${r.slug}.investigation_id = "${r.investigation_id}"  // ${r.claim_count} claims · ${Math.round(r.duration_ms / 1000)}s\n`,
    );
  }
}

async function main(): Promise<void> {
  const queue = ONLY.length
    ? DEMO_TARGETS.filter((d) => ONLY.includes(d.slug))
    : DEMO_TARGETS;
  if (queue.length === 0) {
    process.stderr.write("Ningún demo coincide con ONLY=...\n");
    process.exit(2);
  }

  process.stdout.write(`\nPre-cache de ${queue.length} demo(s) contra ${API_BASE}\n`);
  process.stdout.write(`Timeout por demo: ${Math.round(TIMEOUT_MS / 1000)}s\n\n`);

  const results: PreCacheResult[] = [];
  for (const target of queue) {
    process.stdout.write(`▶ ${target.name}  (${target.category})\n`);
    results.push(await runOne(target));
  }

  const okCount = results.filter((r) => r.ok).length;
  process.stdout.write(`\n──── Resumen ────\n`);
  for (const r of results) {
    process.stdout.write(
      `  ${r.ok ? "✓" : "✗"} ${r.slug.padEnd(20)} ${r.investigation_id || "—".padEnd(36)} ${r.claim_count} claims  ${r.reason ?? ""}\n`,
    );
  }
  process.stdout.write(`\n${okCount}/${results.length} OK\n`);

  if (okCount > 0) printPatch(results);

  if (okCount < results.length) process.exit(1);
}

main().catch((err) => {
  process.stderr.write(`fatal: ${err instanceof Error ? err.stack ?? err.message : String(err)}\n`);
  process.exit(1);
});
