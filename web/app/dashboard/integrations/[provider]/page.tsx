import { notFound } from "next/navigation";

import { resolveTenant } from "@/lib/auth/tenant";
import { getIntegration, PROVIDERS, type Provider } from "@/lib/db/queries";
import { CONFIG_FIELDS, SECRET_FIELDS } from "@/lib/crypto/seal";
import { Crumb, StatusPill } from "@/components/ui";
import { IntegrationForm } from "@/components/integration-form";

export default async function ProviderPage({
  params,
}: {
  params: Promise<{ provider: string }>;
}) {
  const { provider } = await params;
  if (!PROVIDERS.includes(provider as Provider)) notFound();
  const p = provider as Provider;

  const tenant = await resolveTenant();
  const integration = await getIntegration(tenant.id, p);

  return (
    <div style={{ paddingTop: 24, maxWidth: 620 }}>
      <Crumb href="/dashboard/integrations">Integrations</Crumb>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 12 }}>
        <h1 style={{ fontSize: 30, textTransform: "capitalize" }}>{p}</h1>
        <StatusPill status={integration?.status ?? "unconfigured"} />
      </div>

      {integration?.statusDetail && Object.keys(integration.statusDetail).length > 0 ? (
        <pre className="logbox" style={{ marginTop: 16, maxHeight: 160 }}>
          {JSON.stringify(integration.statusDetail, null, 2)}
        </pre>
      ) : null}

      <IntegrationForm
        provider={p}
        configFields={CONFIG_FIELDS[p] ?? []}
        secretFields={SECRET_FIELDS[p] ?? []}
        config={(integration?.config ?? {}) as Record<string, string>}
        hasSecret={Object.fromEntries(
          (SECRET_FIELDS[p] ?? []).map((f) => [f, Boolean(integration?.secretsCiphertext?.[f])]),
        )}
        workerReady={Boolean(tenant.workerPublicKey)}
      />
    </div>
  );
}
