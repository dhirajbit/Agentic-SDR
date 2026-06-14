import Link from "next/link";

import { resolveTenant } from "@/lib/auth/tenant";
import { getCycleRuns } from "@/lib/db/queries";
import { StatusPill } from "@/components/ui";

export default async function CyclesPage() {
  const tenant = await resolveTenant();
  const runs = await getCycleRuns(tenant.id, 50);

  return (
    <div style={{ paddingTop: 24 }}>
      <h1 style={{ fontSize: 30 }}>Cycles</h1>
      <div className="panel" style={{ marginTop: 16, overflowX: "auto" }}>
        <table className="feed">
          <thead>
            <tr>
              <th>Started</th>
              <th>Kind</th>
              <th>Trigger</th>
              <th>Status</th>
              <th>Finished</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {runs.length === 0 ? (
              <tr>
                <td colSpan={6} className="muted">
                  No cycles yet.
                </td>
              </tr>
            ) : (
              runs.map((r) => (
                <tr key={r.id}>
                  <td className="mono" style={{ whiteSpace: "nowrap" }}>
                    {r.startedAt ? new Date(r.startedAt).toLocaleString() : "—"}
                  </td>
                  <td>{r.kind}</td>
                  <td className="muted">{r.trigger}</td>
                  <td>
                    <StatusPill status={r.status} />
                  </td>
                  <td className="mono muted" style={{ whiteSpace: "nowrap" }}>
                    {r.finishedAt ? new Date(r.finishedAt).toLocaleTimeString() : ""}
                  </td>
                  <td>
                    <Link href={`/dashboard/cycles/${r.id}`} className="mono" style={{ fontSize: 12 }}>
                      view →
                    </Link>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
