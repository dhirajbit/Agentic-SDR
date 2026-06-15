import Link from "next/link";

import { resolveTenant } from "@/lib/auth/tenant";
import { getRecentActions } from "@/lib/db/queries";
import { StatusPill } from "@/components/ui";

export default async function LogsPage({
  searchParams,
}: {
  searchParams: Promise<{ channel?: string; view?: string }>;
}) {
  const { channel, view } = await searchParams;
  const tenant = await resolveTenant();
  const ch = channel === "email" || channel === "whatsapp" ? channel : undefined;
  const scheduled = view === "scheduled";
  const rows = await getRecentActions(tenant.id, {
    channel: ch,
    status: scheduled ? "scheduled" : undefined,
    limit: 300,
  });

  const tab = (params: string, label: string, active: boolean) => (
    <Link
      href={params ? `/dashboard/logs?${params}` : "/dashboard/logs"}
      className="pill"
      style={{ background: active ? "var(--elevated)" : "transparent" }}
    >
      {label}
    </Link>
  );

  return (
    <div style={{ paddingTop: 24 }}>
      <h1 style={{ fontSize: 30 }}>Logs</h1>
      <div style={{ display: "flex", gap: 8, marginTop: 16, flexWrap: "wrap" }}>
        {tab("", "All", !ch && !scheduled)}
        {tab("channel=email", "Email", ch === "email" && !scheduled)}
        {tab("channel=whatsapp", "WhatsApp", ch === "whatsapp" && !scheduled)}
        {tab("view=scheduled", "Scheduled queue", scheduled)}
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
