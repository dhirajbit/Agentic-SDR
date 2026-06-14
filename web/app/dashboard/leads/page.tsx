import { resolveTenant } from "@/lib/auth/tenant";
import { getLeadCounts, getLeadsByStatus } from "@/lib/db/queries";
import { Section, StatTile } from "@/components/ui";

export default async function LeadsPage() {
  const tenant = await resolveTenant();
  const [counts, urgent, blocked] = await Promise.all([
    getLeadCounts(tenant.id),
    getLeadsByStatus(tenant.id, "urgent", 50),
    getLeadsByStatus(tenant.id, "blocked", 50),
  ]);

  const table = (rows: typeof urgent, emptyMsg: string) => (
    <div className="panel" style={{ overflowX: "auto" }}>
      <table className="feed">
        <thead>
          <tr>
            <th>Company</th>
            <th>Email</th>
            <th>Mobile</th>
            <th>Updated</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={4} className="muted">
                {emptyMsg}
              </td>
            </tr>
          ) : (
            rows.map((l) => (
              <tr key={l.id}>
                <td>{l.company}</td>
                <td className="mono">{l.email}</td>
                <td className="mono">{l.mobile}</td>
                <td className="mono muted">{new Date(l.updatedAt).toLocaleString()}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );

  return (
    <div style={{ paddingTop: 24 }}>
      <h1 style={{ fontSize: 30 }}>Leads</h1>
      <div className="grid grid-3" style={{ marginTop: 16 }}>
        <StatTile label="Queued" value={counts.queued} />
        <StatTile label="Blocked / opted-out" value={counts.blocked} />
        <StatTile label="Urgent follow-ups" value={counts.urgent} />
      </div>

      <Section title="Urgent follow-ups">{table(urgent, "Nothing urgent.")}</Section>
      <Section title="Blocked / opted-out">{table(blocked, "No blocked leads.")}</Section>
    </div>
  );
}
