import { cookies } from "next/headers";
import { createServerClient as createSupabaseServerClient, type CookieOptions } from "@supabase/ssr";

function readSupabaseEnv() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) return null;
  return { url, key };
}

export async function createServerClient() {
  const env = readSupabaseEnv();
  if (!env) return null;

  const cookieStore = await cookies();

  return createSupabaseServerClient(env.url, env.key, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet: { name: string; value: string; options: CookieOptions }[]) {
        try {
          cookiesToSet.forEach(({ name, value, options }) => {
            cookieStore.set(name, value, options);
          });
        } catch {
          // Called from a Server Component — the proxy refreshes the cookies instead.
        }
      },
    },
  });
}

export async function getCurrentUser() {
  const supabase = await createServerClient();
  if (!supabase) return null;
  const {
    data: { user },
  } = await supabase.auth.getUser();
  return user;
}
