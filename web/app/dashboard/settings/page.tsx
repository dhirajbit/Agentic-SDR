import { resolveTenant } from "@/lib/auth/tenant";
import { getSettings, getPendingCommands } from "@/lib/db/queries";
import { Section } from "@/components/ui";
import { WorkerBadge } from "@/components/worker-badge";
import { SettingsControls } from "@/components/settings-controls";

export default async function SettingsPage() {
  const tenant = await resolveTenant();
  const [settings, pending] = await Promise.all([
    getSettings(tenant.id),
    getPendingCommands(tenant.id),
  ]);

  return (
    <div style={{ paddingTop: 24, maxWidth: 680 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <h1 style={{ fontSize: 30 }}>Settings & controls</h1>
        <WorkerBadge lastSeenAt={tenant.workerLastSeenAt} />
      </div>

      <Section title="Send controls">
        <SettingsControls
          liveSend={settings?.liveSend ?? false}
          autoLoop={settings?.autoLoop ?? false}
          canRun={tenant.driver === "sdr_cycle"}
          driver={tenant.driver}
        />
      </Section>

      {pending.length > 0 ? (
        <Section title="Queued for worker">
          <div className="panel">
            {pending.map((c) => (
              <div key={c.id} className="mono" style={{ fontSize: 12, padding: "4px 0" }}>
                {c.type} {JSON.stringify(c.args)} ·{" "}
                <span className="muted">{new Date(c.createdAt).toLocaleTimeString()}</span>
              </div>
            ))}
            <p className="muted mono" style={{ fontSize: 11, marginTop: 8 }}>
              These run when the local worker next checks in.
            </p>
          </div>
        </Section>
      ) : null}
    </div>
  );
}
