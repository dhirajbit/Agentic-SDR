import { notFound } from "next/navigation";

import { resolveTenant } from "@/lib/auth/tenant";
import { getCycleRun } from "@/lib/db/queries";
import { Crumb, StatusPill } from "@/components/ui";
import { LiveLogTail } from "@/components/live-log-tail";

export default async function CycleRunPage({
  params,
}: {
  params: Promise<{ runId: string }>;
}) {
  const { runId } = await params;
  const tenant = await resolveTenant();
  const run = await getCycleRun(tenant.id, runId);
  if (!run) notFound();

  const live = run.status === "running" || run.status === "pending";

  return (
    <div style={{ paddingTop: 24 }}>
      <Crumb href="/dashboard/cycles">Cycles</Crumb>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 12 }}>
        <h1 style={{ fontSize: 30, textTransform: "capitalize" }}>{run.kind} cycle</h1>
        <StatusPill status={run.status} />
      </div>
      <p className="muted mono" style={{ fontSize: 12, marginTop: 8 }}>
        {run.startedAt ? new Date(run.startedAt).toLocaleString() : "not started"} · trigger:{" "}
        {run.trigger ?? "—"}
      </p>

      {run.summary ? (
        <pre className="logbox" style={{ marginTop: 16, maxHeight: 200 }}>
          {JSON.stringify(run.summary, null, 2)}
        </pre>
      ) : null}

      <h2 style={{ fontSize: 18, marginTop: 24 }}>Log</h2>
      {live ? (
        <LiveLogTail runId={run.id} initialLog={run.log ?? ""} />
      ) : (
        <pre className="logbox" style={{ marginTop: 12 }}>
          {run.log || "(no log captured)"}
        </pre>
      )}
    </div>
  );
}
