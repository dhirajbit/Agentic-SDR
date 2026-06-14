import Link from "next/link";

import { resolveTenant } from "@/lib/auth/tenant";
import { getIntegrations } from "@/lib/db/queries";
import { ProviderIcon, Section, StatusPill } from "@/components/ui";

function detailLine(provider: string, detail: Record<string, unknown> | null): string {
  if (!detail) return "";
  if (provider === "apollo" && detail.credits_left != null) return `${detail.credits_left} credits`;
  if (provider === "whatsapp" && detail.session_status)
    return `${detail.session_status}${detail.phone ? ` · ${detail.phone}` : ""}`;
  if (detail.last_error) return String(detail.last_error);
  return "";
}

export default async function IntegrationsPage() {
  const tenant = await resolveTenant();
  const integrations = await getIntegrations(tenant.id);

  return (
    <div style={{ paddingTop: 24 }}>
      <h1 style={{ fontSize: 30 }}>Integrations</h1>
      <p className="muted" style={{ marginTop: 8 }}>
        Keys are encrypted in your browser and only decryptable by your local worker. This app
        never stores plaintext secrets.
      </p>

      <Section title="Connected tools">
        <div className="grid grid-2">
          {integrations.map((i) => (
            <Link
              key={i.id}
              href={`/dashboard/integrations/${i.provider}`}
              className="panel"
              style={{ display: "flex", alignItems: "center", gap: 14 }}
            >
              <ProviderIcon provider={i.provider} size={28} />
              <div>
                <div style={{ textTransform: "capitalize", fontWeight: 600 }}>{i.provider}</div>
                <div className="muted mono" style={{ fontSize: 11 }}>
                  {detailLine(i.provider, i.statusDetail) ||
                    (i.lastCheckedAt
                      ? `checked ${new Date(i.lastCheckedAt).toLocaleString()}`
                      : "not checked")}
                </div>
              </div>
              <div style={{ marginLeft: "auto" }}>
                <StatusPill status={i.status} />
              </div>
            </Link>
          ))}
        </div>
      </Section>
    </div>
  );
}
