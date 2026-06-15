import Link from "next/link";

import { resolveTenant } from "@/lib/auth/tenant";
import { getRecentActions } from "@/lib/db/queries";
import { LogTable } from "@/components/log-table";

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
        <LogTable
          rows={rows.map((a) => ({
            id: a.id,
            occurredAt: new Date(a.occurredAt).toISOString(),
            channel: a.channel,
            company: a.company,
            recipient: a.recipient,
            framework: a.framework,
            subject: a.subject,
            body: a.body,
            status: a.status,
          }))}
        />
      </div>
    </div>
  );
}
