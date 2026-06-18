import Link from "next/link";

import { resolveTenant } from "@/lib/auth/tenant";
import { getCampaigns, getRecentActions } from "@/lib/db/queries";
import { LogTable } from "@/components/log-table";

export default async function LogsPage({
  searchParams,
}: {
  searchParams: Promise<{ channel?: string; view?: string; campaign?: string }>;
}) {
  const { channel, view, campaign } = await searchParams;
  const tenant = await resolveTenant();
  const ch = channel === "email" || channel === "whatsapp" ? channel : undefined;
  const scheduled = view === "scheduled";

  const campaigns = await getCampaigns(tenant.id);
  const activeCampaign = campaign && campaigns.includes(campaign) ? campaign : undefined;

  const rows = await getRecentActions(tenant.id, {
    channel: ch,
    status: scheduled ? "scheduled" : undefined,
    campaign: activeCampaign,
    limit: 300,
  });

  // Build a Logs URL from explicit params (drops falsy ones). Channel/view pills
  // keep the chosen campaign; campaign pills keep the chosen channel/view.
  const mk = (params: Record<string, string | undefined>) => {
    const sp = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v) sp.set(k, v);
    const qs = sp.toString();
    return qs ? `/dashboard/logs?${qs}` : "/dashboard/logs";
  };
  const viewParam = scheduled ? "scheduled" : undefined;

  const tab = (href: string, label: string, active: boolean) => (
    <Link
      href={href}
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
        {tab(mk({ campaign: activeCampaign }), "All", !ch && !scheduled)}
        {tab(mk({ channel: "email", campaign: activeCampaign }), "Email", ch === "email" && !scheduled)}
        {tab(mk({ channel: "whatsapp", campaign: activeCampaign }), "WhatsApp", ch === "whatsapp" && !scheduled)}
        {tab(mk({ view: "scheduled", campaign: activeCampaign }), "Scheduled queue", scheduled)}
      </div>

      {campaigns.length > 0 ? (
        <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap", alignItems: "center" }}>
          <span className="stat-label" style={{ marginRight: 2 }}>Campaign</span>
          {tab(mk({ channel: ch, view: viewParam }), "All campaigns", !activeCampaign)}
          {campaigns.map((c) =>
            tab(mk({ channel: ch, view: viewParam, campaign: c }), c, activeCampaign === c),
          )}
        </div>
      ) : null}

      <div className="panel" style={{ marginTop: 16, overflowX: "auto" }}>
        <LogTable
          rows={rows.map((a) => ({
            id: a.id,
            occurredAt: new Date(a.occurredAt).toISOString(),
            channel: a.channel,
            campaign: (a.events as { campaign?: string } | null)?.campaign ?? null,
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
