import { createClient, SupabaseClient } from "@supabase/supabase-js";

let _client: SupabaseClient | null = null;

/**
 * Lazy-init Supabase client. We can't init at module load time because
 * Next.js page-data collection runs at build time when env vars aren't set.
 * Calling code uses `db()` instead of importing a constant.
 */
export function db(): SupabaseClient {
  if (_client) return _client;
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) {
    throw new Error("[supabase] missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY");
  }
  _client = createClient(url, key, { auth: { persistSession: false } });
  return _client;
}

// Backwards-compat alias for code that already imported `supabase`.
// Throws lazily on first method call. Binds methods so `this` works correctly.
export const supabase = new Proxy({} as SupabaseClient, {
  get(_t, prop) {
    const client = db() as any;
    const v = client[prop];
    return typeof v === "function" ? v.bind(client) : v;
  },
});
