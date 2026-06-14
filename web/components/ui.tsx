/** Small presentational helpers shared across dashboard pages. */
import Link from "next/link";

export function StatTile({ label, value, sub }: { label: string; value: React.ReactNode; sub?: string }) {
  return (
    <div className="panel">
      <div className="stat-label">{label}</div>
      <div className="stat-num" style={{ marginTop: 8 }}>
        {value}
      </div>
      {sub ? (
        <div className="muted mono" style={{ fontSize: 11, marginTop: 6 }}>
          {sub}
        </div>
      ) : null}
    </div>
  );
}

export function StatusPill({ status }: { status: string }) {
  const ok = status === "connected" || status === "ready" || status === "done";
  const warn = status === "error" || status === "failed" || status === "send_failed";
  const cls = ok ? "pill ok" : warn ? "pill warn" : "pill";
  return (
    <span className={cls}>
      <span className="dot" />
      {status}
    </span>
  );
}

const PROVIDER_DOMAIN: Record<string, string | null> = {
  apollo: "apollo.io",
  brevo: "brevo.com",
  zoho: "zoho.com",
  whatsapp: "whatsapp.com",
  gemini: "gemini.google.com",
  erpnext: "erpnext.com",
};

export function ProviderIcon({ provider, size = 20 }: { provider: string; size?: number }) {
  const domain = PROVIDER_DOMAIN[provider];
  if (!domain) return null;
  // eslint-disable-next-line @next/next/no-img-element
  return (
    <img
      src={`https://www.google.com/s2/favicons?domain=${domain}&sz=64`}
      alt={provider}
      width={size}
      height={size}
      style={{ borderRadius: 4 }}
    />
  );
}

export function Section({ title, action, children }: { title: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section style={{ marginTop: 28 }}>
      <div style={{ display: "flex", alignItems: "center", marginBottom: 12 }}>
        <h2 style={{ fontSize: 20 }}>{title}</h2>
        {action ? <div style={{ marginLeft: "auto" }}>{action}</div> : null}
      </div>
      {children}
    </section>
  );
}

export function Crumb({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link href={href} className="mono muted" style={{ fontSize: 12 }}>
      ← {children}
    </Link>
  );
}
