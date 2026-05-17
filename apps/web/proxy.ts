import { NextResponse, type NextRequest } from "next/server";

import { createServerClient } from "@/lib/supabase/proxy";

/**
 * Next 16 proxy (formerly `middleware`). Refreshes the Supabase session cookies
 * on every request so Server Components see an up-to-date user, and passes the
 * request through unchanged otherwise.
 */
export async function proxy(request: NextRequest) {
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
