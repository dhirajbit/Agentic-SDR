import Link from "next/link";

import { resolveTenant } from "@/lib/auth/tenant";
import { getRecentActions } from "@/lib/db/queries";
import { StatusPill } from "@/components/ui";

export default async function LogsPage({
  searchParams,
}: {
  searchParams: Promise<{ channel?: string }>;
}) {
  const { channel } = await searchParams;
  const tenant = await resolveTenant();
  const ch = channel === "email" || channel === "whatsapp" ? channel : undefined;
  const rows = await getRecentActions(tenant.id, { channel: ch, limit: 200 });

  const tab = (key: string, label: string) => (
    <Link
      href={key ? `/dashboard/logs?channel=${key}` : "/dashboard/logs"}
      className="pill"
      style={{ background: (ch ?? "") === key ? "var(--elevated)" : "transparent" }}
    >
      {label}
    </Link>
  );

  return (
    <div style={{ paddingTop: 24 }}>
      <h1 style={{ fontSize: 30 }}>Logs</h1>
      <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
        {tab("", "All")}
        {tab("email", "Email")}
        {tab("whatsapp", "WhatsApp")}
      </div>

      <div className="panel" style={{ marginTop: 16, overflowX: "auto" }}>
        <table className="feed">
          <thead>
            <tr>
              <th>When</th>
              <th>Channel</th>
              <th>Company</th>
              <th>Recipient</th>
              <th>Framework</th>
              <th>Subject / message</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={7} className="muted">
                  No actions logged yet.
                </td>
              </tr>
            ) : (
              rows.map((a) => (
                <tr key={a.id}>
                  <td className="mono" style={{ whiteSpace: "nowrap" }}>
                    {new Date(a.occurredAt).toLocaleString()}
                  </td>
                  <td>
                    <span className={a.channel === "whatsapp" ? "pill warn" : "pill"}>
                      {a.channel}
                    </span>
                  </td>
                  <td>{a.company}</td>
                  <td className="mono">{a.recipient}</td>
                  <td>{a.framework}</td>
                  <td style={{ maxWidth: 320 }}>{a.subject || a.body?.slice(0, 80)}</td>
                  <td>{a.status ? <StatusPill status={a.status} /> : null}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
