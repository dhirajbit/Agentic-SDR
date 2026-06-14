import { auth } from "@clerk/nextjs/server";
import { CreateOrganization, OrganizationSwitcher } from "@clerk/nextjs";
import { redirect } from "next/navigation";

import { tryResolveTenant } from "@/lib/auth/tenant";
import { provisionTenant } from "@/lib/actions/onboarding";

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

  // Org exists. Provision the tenant row if missing, then enter the console.
  const existing = await tryResolveTenant();
  if (existing) redirect("/dashboard");

  return (
    <main className="wrap" style={{ paddingTop: 64, maxWidth: 560 }}>
      <h1 style={{ fontSize: 32 }}>Set up this tenant</h1>
      <p className="muted" style={{ marginTop: 12 }}>
        Organization <strong>{orgSlug}</strong> isn&apos;t linked to an SDR tenant yet.
      </p>
      <form action={provisionTenant} style={{ marginTop: 24 }}>
        <button className="btn primary" type="submit">
          Link &amp; open console
        </button>
      </form>
      <p className="muted mono" style={{ marginTop: 16, fontSize: 12 }}>
        Note: a matching local worker directory (tenants/{orgSlug}/) must exist for cycles to
        run. See SAAS_SETUP.md.
      </p>
    </main>
  );
}
