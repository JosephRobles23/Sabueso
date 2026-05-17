/**
 * Edge rate-limit middleware backed by Vercel KV (Upstash Redis under the hood).
 *
 * Buckets (S-20):
 *   - anon  : 10/IP/24h        (any anonymous request that hits a rate-limited path)
 *   - auth  : 50/user/24h      (authenticated by Supabase user-id cookie)
 *   - search: 300/IP/1h        (cheap GET endpoints under /api/search)
 *   - pdf   : 20/IP/24h        (POST /api/export-pdf — expensive Playwright job)
 *
 * Counters are incremented atomically via INCR; the first writer in a window
 * also sets EXPIRE so keys self-clean. On a Vercel KV outage we fail-open
 * (log + allow) — rate limiting is a guardrail, not auth.
 *
 * Next 16 renamed `middleware.ts` to `proxy.ts`, so the actual entry point lives
 * in `proxy.ts`; it imports `rateLimitEdge` from here and chains it before the
 * Supabase session refresh.
 */
import { NextResponse, type NextRequest } from "next/server";

export const RATE_LIMITS = {
  anon: { limit: 10, windowSeconds: 60 * 60 * 24 }, // 10 / IP / 24h
  auth: { limit: 50, windowSeconds: 60 * 60 * 24 }, // 50 / user / 24h
  search: { limit: 300, windowSeconds: 60 * 60 }, //   300 / IP / 1h
  pdf: { limit: 20, windowSeconds: 60 * 60 * 24 }, //  20 / IP / 24h
} as const;

export type RateLimitBucket = keyof typeof RATE_LIMITS;

interface KVClient {
  incr(key: string): Promise<number>;
  expire(key: string, seconds: number): Promise<void>;
}

/** Vercel KV REST client — token+url come from VERCEL_KV_REST_API_URL / TOKEN. */
class VercelKV implements KVClient {
  constructor(
    private readonly url: string,
    private readonly token: string,
  ) {}

  private async pipeline(commands: (string | number)[][]): Promise<unknown[]> {
    const res = await fetch(`${this.url}/pipeline`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${this.token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(commands),
      // Vercel Edge: no keep-alive needed; runtime pools for us.
      cache: "no-store",
    });
    if (!res.ok) {
      throw new Error(`vercel-kv ${res.status}: ${await res.text()}`);
    }
    const json = (await res.json()) as { result: unknown }[];
    return json.map((r) => r.result);
  }

  async incr(key: string): Promise<number> {
    const [result] = await this.pipeline([["INCR", key]]);
    return Number(result ?? 0);
  }

  async expire(key: string, seconds: number): Promise<void> {
    await this.pipeline([["EXPIRE", key, seconds]]);
  }
}

let _client: KVClient | null = null;

/** Lazy singleton; tests can override via `setKVClient`. */
function getClient(): KVClient | null {
  if (_client) return _client;
  const url = process.env.VERCEL_KV_REST_API_URL;
  const token = process.env.VERCEL_KV_REST_API_TOKEN;
  if (!url || !token) return null;
  _client = new VercelKV(url, token);
  return _client;
}

export function setKVClient(client: KVClient | null): void {
  _client = client;
}

export interface RateLimitDecision {
  allowed: boolean;
  bucket: RateLimitBucket;
  limit: number;
  remaining: number;
  resetSeconds: number;
  identifier: string;
}

/**
 * Map a request to (bucket, identifier). Returns null for paths that aren't
 * rate-limited (most of the app — static, public pages, etc.).
 */
export function classify(request: NextRequest): {
  bucket: RateLimitBucket;
  identifier: string;
} | null {
  const { pathname } = request.nextUrl;

  const userId = request.cookies.get("sb-user-id")?.value;
  const ip = clientIp(request);

  if (pathname.startsWith("/api/export-pdf")) {
    return { bucket: "pdf", identifier: `ip:${ip}` };
  }
  if (pathname.startsWith("/api/search")) {
    return { bucket: "search", identifier: `ip:${ip}` };
  }
  if (pathname.startsWith("/api/investigate")) {
    return userId
      ? { bucket: "auth", identifier: `user:${userId}` }
      : { bucket: "anon", identifier: `ip:${ip}` };
  }
  return null;
}

function clientIp(request: NextRequest): string {
  // Vercel sets `x-forwarded-for` as a comma-separated list; first entry is the client.
  const fwd = request.headers.get("x-forwarded-for");
  if (fwd) return fwd.split(",")[0]!.trim();
  return request.headers.get("x-real-ip") ?? "0.0.0.0";
}

function bucketWindowKey(bucket: RateLimitBucket, identifier: string): string {
  const window = RATE_LIMITS[bucket].windowSeconds;
  // Bucket window aligned to wall clock so all clients in a window share the
  // same key (cheaper than per-request sliding windows; sufficient for S-20).
  const slot = Math.floor(Date.now() / 1000 / window);
  return `rl:${bucket}:${identifier}:${slot}`;
}

/**
 * Hit the limiter for the inferred bucket. Returns a decision; the caller is
 * responsible for translating `!allowed` into a 429 response (so the same
 * function can be reused server-side without coupling to NextResponse).
 */
export async function checkRateLimit(
  request: NextRequest,
): Promise<RateLimitDecision | null> {
  const cls = classify(request);
  if (!cls) return null;

  const cfg = RATE_LIMITS[cls.bucket];
  const client = getClient();
  if (!client) {
    // Fail-open in environments without KV configured (local dev, preview).
    return {
      allowed: true,
      bucket: cls.bucket,
      limit: cfg.limit,
      remaining: cfg.limit,
      resetSeconds: cfg.windowSeconds,
      identifier: cls.identifier,
    };
  }

  const key = bucketWindowKey(cls.bucket, cls.identifier);

  try {
    const count = await client.incr(key);
    if (count === 1) {
      // First request in this window — set TTL so keys don't leak forever.
      await client.expire(key, cfg.windowSeconds);
    }
    const remaining = Math.max(0, cfg.limit - count);
    return {
      allowed: count <= cfg.limit,
      bucket: cls.bucket,
      limit: cfg.limit,
      remaining,
      resetSeconds: cfg.windowSeconds,
      identifier: cls.identifier,
    };
  } catch (err) {
    // Network/Upstash blip: fail-open + structured log for the platform team.
    console.warn("[rate-limit] kv error, failing open", {
      bucket: cls.bucket,
      identifier: cls.identifier,
      error: err instanceof Error ? err.message : String(err),
    });
    return {
      allowed: true,
      bucket: cls.bucket,
      limit: cfg.limit,
      remaining: cfg.limit,
      resetSeconds: cfg.windowSeconds,
      identifier: cls.identifier,
    };
  }
}

/** Build the 429 response (with Retry-After + RateLimit-* headers). */
export function rateLimited(decision: RateLimitDecision): NextResponse {
  const res = NextResponse.json(
    {
      error: "rate_limited",
      detail: `Has alcanzado el límite de ${decision.limit} solicitudes para esta acción. Intenta nuevamente en unos minutos.`,
      bucket: decision.bucket,
    },
    { status: 429 },
  );
  applyRateLimitHeaders(res, decision);
  res.headers.set("Retry-After", String(decision.resetSeconds));
  return res;
}

export function applyRateLimitHeaders(res: NextResponse, decision: RateLimitDecision): void {
  res.headers.set("X-RateLimit-Limit", String(decision.limit));
  res.headers.set("X-RateLimit-Remaining", String(decision.remaining));
  res.headers.set("X-RateLimit-Bucket", decision.bucket);
}

/**
 * Edge middleware entry point. Returns a 429 response if the request is
 * over-limit; otherwise returns null (caller continues the chain). Designed to
 * be invoked from `proxy.ts` (Next 16's renamed middleware entry).
 */
export async function rateLimitEdge(request: NextRequest): Promise<NextResponse | null> {
  const decision = await checkRateLimit(request);
  if (!decision) return null;
  if (!decision.allowed) return rateLimited(decision);
  return null;
}

// Same matcher Next 16 expects on the entry file. Re-exported so that if the
// project ever flips back to middleware.ts as the entry point, it just works.
export const config = {
  matcher: ["/api/investigate/:path*", "/api/search/:path*", "/api/export-pdf/:path*"],
};
