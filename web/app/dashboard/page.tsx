import Link from "next/link";

import { resolveTenant } from "@/lib/auth/tenant";
import {
  getAggregateStats,
  getCycleRuns,
  getIntegrations,
  getLatestCredit,
  getLeadCounts,
} from "@/lib/db/queries";
import { ProviderIcon, Section, StatTile, StatusPill } from "@/components/ui";
import { WorkerBadge } from "@/components/worker-badge";

export default async function OverviewPage() {
  const tenant = await resolveTenant();
  const [stats, leadCounts, runs, integrations, credit] = await Promise.all([
    getAggregateStats(tenant.id),
    getLeadCounts(tenant.id),
    getCycleRuns(tenant.id, 5),
    getIntegrations(tenant.id),
    getLatestCredit(tenant.id),
  ]);

  const replyRate = stats.sent ? Math.round((stats.replied / stats.sent) * 100) : 0;
  const openRate = stats.sent ? Math.round((stats.opened / stats.sent) * 100) : 0;

  return (
    <div style={{ paddingTop: 24 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <h1 style={{ fontSize: 30 }}>{tenant.name}</h1>
        <WorkerBadge lastSeenAt={tenant.workerLastSeenAt} />
      </div>

      <div className="grid grid-4" style={{ marginTop: 20 }}>
        <StatTile label="Emails sent" value={stats.emails} sub={`${stats.sent} delivered`} />
        <StatTile label="WhatsApp touches" value={stats.whatsapp} />
        <StatTile label="Open rate" value={`${openRate}%`} sub={`${stats.opened} opened`} />
        <StatTile label="Reply rate" value={`${replyRate}%`} sub={`${stats.replied} replies`} />
      </div>

      <div className="grid grid-4" style={{ marginTop: 16 }}>
        <StatTile label="Queue depth" value={leadCounts.queued} />
        <StatTile label="Blocked / opted-out" value={leadCounts.blocked} />
        <StatTile label="Urgent follow-ups" value={leadCounts.urgent} />
        <StatTile
          label="Apollo credits"
          value={credit?.leadCreditLeft ?? "—"}
          sub={credit ? `as of ${new Date(credit.at).toLocaleDateString()}` : "no snapshot"}
        />
      </div>

      <Section
        title="Integrations"
        action={
          <Link href="/dashboard/integrations" className="mono muted" style={{ fontSize: 12 }}>
            manage →
          </Link>
        }
      >
        <div className="grid grid-3">
          {integrations.map((i) => (
            <div
              key={i.id}
              className="panel"
              style={{ display: "flex", alignItems: "center", gap: 12 }}
            >
              <ProviderIcon provider={i.provider} />
              <div style={{ textTransform: "capitalize", fontWeight: 600 }}>{i.provider}</div>
              <div style={{ marginLeft: "auto" }}>
                <StatusPill status={i.status} />
              </div>
            </div>
          ))}
        </div>
      </Section>

      <Section
        title="Recent cycles"
        action={
          <Link href="/dashboard/cycles" className="mono muted" style={{ fontSize: 12 }}>
            history →
          </Link>
        }
      >
        {runs.length === 0 ? (
          <p className="muted">No cycles yet.</p>
        ) : (
          <table className="feed">
            <thead>
              <tr>
                <th>Started</th>
                <th>Kind</th>
                <th>Status</th>
                <th>Summary</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id}>
                  <td className="mono">
                    {r.startedAt ? new Date(r.startedAt).toLocaleString() : "—"}
                  </td>
                  <td>{r.kind}</td>
                  <td>
                    <StatusPill status={r.status} />
                  </td>
                  <td className="muted">
                    {r.summary ? JSON.stringify(r.summary) : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Section>
    </div>
  );
}
