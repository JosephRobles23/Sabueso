import { NextResponse, type NextRequest } from "next/server";

import { createServerClient } from "@/lib/supabase/proxy";
import { rateLimitEdge } from "./middleware";

/**
 * Next 16 proxy (formerly `middleware`).
 *
 * Chain (in order):
 *   1. Edge rate-limit (Vercel KV) — 429 short-circuit if over budget.
 *   2. Supabase session refresh so Server Components see an up-to-date user.
 *
 * The rate-limit logic lives in ./middleware.ts so it can be unit-tested in
 * isolation and reused server-side from API routes.
 */
export async function proxy(request: NextRequest) {
  const limited = await rateLimitEdge(request);
  if (limited) return limited;

  const { response } = await createServerClient(request);
  return response;
}

export const config = {
  matcher: [
    // Skip static assets and Next internals
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};

export { NextResponse };
