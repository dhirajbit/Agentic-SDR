/**
 * Server-side OpenWA client for the hosted gateway. Lets the web app create a
 * WhatsApp session per tenant and fetch its QR directly, so the dashboard shows
 * the QR instantly on "Connect WhatsApp" — no local worker/laptop needed.
 *
 * Configured via OPENWA_API_URL (public gateway base, incl. /api) + OPENWA_API_KEY
 * (operator-role key). These are operator INFRA credentials (not tenant secrets),
 * so they live as Vercel env vars. When unset, callers fall back to the worker
 * relay path.
 */
const BASE = process.env.OPENWA_API_URL?.replace(/\/$/, "");
const KEY = process.env.OPENWA_API_KEY;

export function openwaEnabled(): boolean {
  return Boolean(BASE && KEY);
}

async function call<T = unknown>(path: string, init?: RequestInit): Promise<T> {
  if (!BASE || !KEY) throw new Error("OpenWA not configured (OPENWA_API_URL/OPENWA_API_KEY).");
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", "X-API-Key": KEY, ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`OpenWA ${init?.method ?? "GET"} ${path} -> ${res.status}`);
  return (res.status === 204 ? undefined : await res.json()) as T;
}

type Session = { id: string; name?: string; status?: string; phone?: string | null };

export async function listSessions(): Promise<Session[]> {
  const r = await call<Session[] | { sessions?: Session[]; data?: Session[] }>("/sessions");
  return Array.isArray(r) ? r : (r.sessions ?? r.data ?? []);
}
export async function createSession(name: string): Promise<Session> {
  return call<Session>("/sessions", { method: "POST", body: JSON.stringify({ name }) });
}
export async function startSession(id: string): Promise<void> {
  await call(`/sessions/${id}/start`, { method: "POST" });
}
export async function getSessionStatus(id: string): Promise<Session> {
  return call<Session>(`/sessions/${id}`);
}
export async function getQr(id: string): Promise<{ qrCode?: string; status?: string }> {
  return call(`/sessions/${id}/qr`);
}

type Webhook = { id: string; url: string };
export async function ensureWebhook(id: string, url: string, secret: string): Promise<void> {
  try {
    const r = await call<Webhook[] | { webhooks?: Webhook[]; data?: Webhook[] }>(
      `/sessions/${id}/webhooks`,
    );
    const list = Array.isArray(r) ? r : (r.webhooks ?? r.data ?? []);
    if (list.some((w) => w.url === url)) return;
  } catch {
    /* fall through to create */
  }
  await call(`/sessions/${id}/webhooks`, {
    method: "POST",
    body: JSON.stringify({ url, events: ["message.received"], secret }),
  });
}
