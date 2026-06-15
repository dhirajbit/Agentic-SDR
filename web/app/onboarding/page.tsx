import { auth } from "@clerk/nextjs/server";
import { CreateOrganization, OrganizationSwitcher } from "@clerk/nextjs";
import { redirect } from "next/navigation";

import { tryResolveTenant } from "@/lib/auth/tenant";
import { getUnclaimedTenants, linkTenant, provisionTenant } from "@/lib/actions/onboarding";

// User/org-specific; never statically prerender.
export const dynamic = "force-dynamic";

export default async function OnboardingPage() {
  const { userId, orgId, orgSlug } = await auth();
  if (!userId) redirect("/sign-in");

  // No active organization yet — have the user create/select one.
  if (!orgId) {
    return (
      <main className="wrap" style={{ paddingTop: 64, maxWidth: 560 }}>
        <h1 style={{ fontSize: 32 }}>Create your workspace</h1>
        <p className="muted" style={{ marginTop: 12 }}>
          Each organization maps to one SDR tenant. Create one to continue.
        </p>
        <div style={{ marginTop: 24 }}>
          <CreateOrganization afterCreateOrganizationUrl="/onboarding" />
        </div>
        <div style={{ marginTop: 24 }}>
          <OrganizationSwitcher hidePersonal />
        </div>
      </main>
    );
  }

  // Org exists. If already linked, enter the console.
  const existing = await tryResolveTenant();
  if (existing) redirect("/dashboard");

  const unclaimed = await getUnclaimedTenants();

  return (
    <main className="wrap" style={{ paddingTop: 64, maxWidth: 560 }}>
      <h1 style={{ fontSize: 32 }}>Set up this tenant</h1>
      <p className="muted" style={{ marginTop: 12 }}>
        Organization <strong>{orgSlug}</strong> isn&apos;t linked to an SDR tenant yet.
      </p>

      {unclaimed.length > 0 ? (
        <form action={linkTenant} style={{ marginTop: 24, display: "grid", gap: 14 }}>
          <label style={{ display: "grid", gap: 6 }}>
            <span className="stat-label">Link this organization to tenant</span>
            <select name="slug" className="mono" style={selectStyle} defaultValue={unclaimed[0].slug}>
              {unclaimed.map((t) => (
                <option key={t.slug} value={t.slug}>
                  {t.name} ({t.slug})
                </option>
              ))}
            </select>
          </label>
          <button className="btn primary" type="submit" style={{ justifySelf: "start" }}>
            Link &amp; open console
          </button>
        </form>
      ) : (
        <form action={provisionTenant} style={{ marginTop: 24 }}>
          <p className="muted" style={{ marginBottom: 12 }}>
            No unclaimed tenants found. Create a fresh one for this organization.
          </p>
          <button className="btn primary" type="submit">
            Create &amp; open console
          </button>
        </form>
      )}

      <p className="muted mono" style={{ marginTop: 16, fontSize: 12 }}>
        Note: a matching local worker directory (tenants/&lt;slug&gt;/) must exist for cycles to
        run. See SAAS_SETUP.md.
      </p>
    </main>
  );
}

const selectStyle: React.CSSProperties = {
  padding: "9px 12px",
  border: "1px solid var(--line)",
  borderRadius: "var(--r-sm)",
  fontSize: 13,
  background: "var(--bg)",
};
