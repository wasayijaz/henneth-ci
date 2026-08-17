const JWKS_URL = "https://qteoncckohuoatbjjykb.supabase.co/auth/v1/.well-known/jwks.json";

let keyCache = null;
let keyCacheAt = 0;
const KEY_TTL_MS = 60 * 60 * 1000;

function b64urlToBytes(s) {
  const norm = s.replace(/-/g, "+").replace(/_/g, "/");
  const padded = norm + "=".repeat((4 - (norm.length % 4)) % 4);
  const bin = atob(padded);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

async function getKeys() {
  const now = Date.now();
  if (keyCache && now - keyCacheAt < KEY_TTL_MS) return keyCache;
  const res = await fetch(JWKS_URL, { cf: { cacheTtl: 3600 } });
  if (!res.ok) throw new Error("jwks " + res.status);
  const jwks = await res.json();
  const map = new Map();
  for (const k of jwks.keys || []) {
    if (k.kty !== "EC" || k.crv !== "P-256") continue;
    const key = await crypto.subtle.importKey(
      "jwk", k, { name: "ECDSA", namedCurve: "P-256" }, false, ["verify"]
    );
    map.set(k.kid, key);
  }
  keyCache = map;
  keyCacheAt = now;
  return map;
}

async function verify(token) {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const [h, p, s] = parts;
    const header = JSON.parse(new TextDecoder().decode(b64urlToBytes(h)));
    const payload = JSON.parse(new TextDecoder().decode(b64urlToBytes(p)));
    if (header.alg !== "ES256") return null;
    if (!header.kid) return null;
    if (typeof payload.exp !== "number") return null;
    if (payload.exp * 1000 < Date.now() - 30_000) return null;

    const key = (await getKeys()).get(header.kid);
    if (!key) return null;
    const ok = await crypto.subtle.verify(
      { name: "ECDSA", hash: "SHA-256" },
      key,
      b64urlToBytes(s),
      new TextEncoder().encode(h + "." + p)
    );
    return ok ? payload : null;
  } catch {
    return null;
  }
}

function deny(reason, status = 401) {
  return new Response(JSON.stringify({
    error: status === 403 ? "forbidden" : "owner_required",
    detail: reason,
  }), {
    status,
    headers: {
      "content-type": "application/json",
      "cache-control": "no-store",
      "www-authenticate": "Bearer realm=\"henneth-company-intelligence\"",
    },
  });
}

export const config = {
  matcher: "/data/:path*",
};

export default async function middleware(request) {
  const owner = process.env.CI_OWNER_USER_ID;
  if (!owner) return deny("owner id is not configured");

  const header = request.headers.get("authorization") || "";
  if (!header.startsWith("Bearer ")) return deny("missing bearer token");

  const payload = await verify(header.slice(7).trim());
  if (!payload) return deny("invalid or expired token");
  if (payload.sub !== owner) return deny("account is not the CI owner", 403);

  return;
}
