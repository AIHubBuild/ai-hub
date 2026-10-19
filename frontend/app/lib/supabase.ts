import { createClient, SupabaseClient } from "@supabase/supabase-js";

let cached: SupabaseClient | null | undefined;

export function getSupabase(): SupabaseClient | null {
  if (cached !== undefined) {
    return cached;
  }
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  cached =
    url && anonKey
      ? createClient(url, anonKey, {
          auth: {
            flowType: "pkce",
            detectSessionInUrl: true,
          },
        })
      : null;
  return cached;
}

export async function authHeaders(): Promise<Record<string, string>> {
  const supabase = getSupabase();
  if (supabase === null) {
    return {};
  }
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}
