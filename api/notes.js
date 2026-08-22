/* AUTHENTICATED NOTES PROXY
 *
 * The extension should not need a direct Supabase host permission. This route
 * verifies the caller's Supabase JWT, then forwards only the user's notes
 * read/write to the profiles table. The publishable key is low-privilege and
 * RLS remains the final row-level boundary; no service/secret key is used here.
 */

export const config = { runtime: 'edge' };

const SUPABASE_URL = process.env.SUPABASE_URL || 'https://qteoncckohuoatbjjykb.supabase.co';
const SUPABASE_PUBLISHABLE_KEY = process.env.SUPABASE_PUBLISHABLE_KEY ||
  process.env.SUPABASE_ANON_KEY || 'sb_publishable_aQu8P4yrAY7l8Y0AcLth5g_Z3VceUnw';
const JWKS_URL = SUPABASE_URL + '/auth/v1/.well-known/jwks.json';

function headers(extra) {
  return {
    'content-type': 'application/json',
    'cache-control': 'no-store',
    'access-control-allow-origin': '*',
    'access-control-allow-headers': 'authorization, content-type',
    'access-control-allow-methods': 'GET, PUT, OPTIONS',
    ...(extra || {}),
  };
}

function json(status, body) {
  return new Response(JSON.stringify(body), { status, headers: headers() });
}

function b64urlToBytes(s) {
  const norm = s.replace(/-/g, '+').replace(/_/g, '/');
  const padded = norm + '='.repeat((4 - (norm.length % 4)) % 4);
  const bin = atob(padded);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

let keyCache = null, keyCacheAt = 0;
const KEY_TTL_MS = 60 * 60 * 1000;

async function getKeys() {
  const now = Date.now();
  if (keyCache && now - keyCacheAt < KEY_TTL_MS) return keyCache;
  const res = await fetch(JWKS_URL, { cf: { cacheTtl: 3600 } });
  if (!res.ok) throw new Error('jwks ' + res.status);
  const jwks = await res.json();
  const map = new Map();
  for (const k of jwks.keys || []) {
    if (k.kty !== 'EC' || k.crv !== 'P-256') continue;
    map.set(k.kid, await crypto.subtle.importKey(
      'jwk', k, { name: 'ECDSA', namedCurve: 'P-256' }, false, ['verify']
    ));
  }
  keyCache = map;
  keyCacheAt = now;
  return map;
}

async function verifiedUser(token) {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const [h, p, s] = parts;
    const header = JSON.parse(new TextDecoder().decode(b64urlToBytes(h)));
    const payload = JSON.parse(new TextDecoder().decode(b64urlToBytes(p)));
    if (header.alg !== 'ES256' || !header.kid || typeof payload.exp !== 'number' || !payload.sub) return null;
    if (payload.exp * 1000 < Date.now() - 30_000) return null;
    const key = (await getKeys()).get(header.kid);
    if (!key) return null;
    const valid = await crypto.subtle.verify(
      { name: 'ECDSA', hash: 'SHA-256' }, key, b64urlToBytes(s), new TextEncoder().encode(h + '.' + p)
    );
    return valid ? String(payload.sub) : null;
  } catch {
    return null;
  }
}

function supabaseHeaders(token, extra) {
  return {
    apikey: SUPABASE_PUBLISHABLE_KEY,
    authorization: 'Bearer ' + token,
    ...(extra || {}),
  };
}

async function readNotes(uid, token) {
  const url = SUPABASE_URL + '/rest/v1/profiles?id=eq.' + encodeURIComponent(uid) + '&select=notes';
  const res = await fetch(url, { headers: supabaseHeaders(token) });
  if (res.status === 401) return json(401, { ok: false, error: 'account_required' });
  if (!res.ok) return json(502, { ok: false, error: 'Could not read account notes.' });
  const rows = await res.json();
  return json(200, { ok: true, notes: rows?.[0]?.notes && typeof rows[0].notes === 'object' ? rows[0].notes : {} });
}

function cleanNotes(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) return null;
  const out = {};
  for (const [rawSym, rawText] of Object.entries(input)) {
    const sym = String(rawSym || '').trim().toUpperCase();
    if (!sym || sym.length > 16) continue;
    const text = String(rawText ?? '').trim().slice(0, 5000);
    if (text) out[sym] = text;
  }
  if (JSON.stringify(out).length > 200_000) return null;
  return out;
}

async function writeNotes(uid, token, notes) {
  const url = SUPABASE_URL + '/rest/v1/profiles?id=eq.' + encodeURIComponent(uid);
  const res = await fetch(url, {
    method: 'PATCH',
    headers: supabaseHeaders(token, {
      'content-type': 'application/json',
      // return=representation (not minimal): PostgREST answers 200/204 with res.ok true
      // even when the PATCH matched zero rows (e.g. an account whose profiles row was
      // never created — never assume docs/lifecycle_email.sql's trigger has been applied).
      // Without the returned rows we cannot tell "saved" from "silently discarded".
      Prefer: 'return=representation',
    }),
    body: JSON.stringify({ notes }),
  });
  if (res.status === 401) return json(401, { ok: false, error: 'account_required' });
  if (!res.ok) return json(502, { ok: false, error: 'Could not save account notes.' });
  const rows = await res.json();
  if (!Array.isArray(rows) || rows.length === 0) {
    // Zero rows matched — the note was NOT saved. Report that honestly instead of {ok:true}.
    return json(404, { ok: false, error: 'account_setup_incomplete' });
  }
  return json(200, { ok: true });
}

export default async function handler(request) {
  if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: headers() });
  if (request.method !== 'GET' && request.method !== 'PUT') return json(405, { ok: false, error: 'GET or PUT only' });

  const auth = request.headers.get('authorization') || '';
  if (!auth.startsWith('Bearer ')) return json(401, { ok: false, error: 'account_required' });
  const token = auth.slice(7).trim();
  const uid = await verifiedUser(token);
  if (!uid) return json(401, { ok: false, error: 'account_required' });

  if (request.method === 'GET') return readNotes(uid, token);

  let body;
  try { body = await request.json(); } catch { return json(400, { ok: false, error: 'bad json' }); }
  const notes = cleanNotes(body?.notes);
  if (!notes) return json(400, { ok: false, error: 'invalid notes payload' });
  return writeNotes(uid, token, notes);
}
