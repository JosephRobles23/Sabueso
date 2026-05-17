import { NextResponse, type NextRequest } from "next/server";
import { createServerClient as createSupabaseServerClient, type CookieOptions } from "@supabase/ssr";

export async function createServerClient(request: NextRequest) {
  let response = NextResponse.next({ request });

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  // If Supabase is not configured locally, just pass through.
  if (!url || !key) return { supabase: null, response };

  const supabase = createSupabaseServerClient(url, key, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet: { name: string; value: string; options: CookieOptions }[]) {
        cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
        response = NextResponse.next({ request });
        cookiesToSet.forEach(({ name, value, options }) =>
          response.cookies.set(name, value, options),
        );
      },
    },
  });

  // Touch session so cookies refresh on every request.
  await supabase.auth.getUser();

  return { supabase, response };
}
