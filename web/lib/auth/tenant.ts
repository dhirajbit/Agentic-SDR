/**
 * Tenant resolution + isolation. The tenant is ALWAYS derived from the Clerk
 * active organization server-side; never trust a tenant id from request input.
 */
import { auth } from "@clerk/nextjs/server";
import { eq } from "drizzle-orm";
import { redirect } from "next/navigation";

import { db } from "@/lib/db";
import { tenants, type Tenant } from "@/lib/db/schema";

/**
 * Resolve the current tenant from the Clerk session. Redirects to /onboarding
 * if there's no active org or no provisioned tenant row for it.
 */
export async function resolveTenant(): Promise<Tenant> {
  const { userId, orgId } = await auth();
  if (!userId) redirect("/sign-in");
  if (!orgId) redirect("/onboarding");

  const tenant = await db.query.tenants.findFirst({
    where: eq(tenants.clerkOrgId, orgId),
  });
  if (!tenant) redirect("/onboarding");
  return tenant;
}

/** Non-redirecting variant for places that must handle the missing case (e.g. onboarding). */
export async function tryResolveTenant(): Promise<Tenant | null> {
  const { orgId } = await auth();
  if (!orgId) return null;
  return (
    (await db.query.tenants.findFirst({ where: eq(tenants.clerkOrgId, orgId) })) ?? null
  );
}
