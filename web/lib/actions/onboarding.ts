"use server";

import { auth, clerkClient } from "@clerk/nextjs/server";
import { and, eq, like } from "drizzle-orm";
import { redirect } from "next/navigation";

import { db } from "@/lib/db";
import { integrations, settings, tenants } from "@/lib/db/schema";
import { PROVIDERS } from "@/lib/db/queries";

/** Unclaimed (worker-seeded, not yet linked) tenants the operator can adopt. */
export async function getUnclaimedTenants() {
  return db
    .select({ slug: tenants.slug, name: tenants.name })
    .from(tenants)
    .where(like(tenants.clerkOrgId, "pending:%"))
    .orderBy(tenants.slug);
}

async function seedTenantChildren(tenantId: string) {
  await db
    .insert(integrations)
    .values(PROVIDERS.map((provider) => ({ tenantId, provider })))
    .onConflictDoNothing();
  await db.insert(settings).values({ tenantId }).onConflictDoNothing();
}

/**
 * Link the active Clerk org to a specific worker-seeded tenant chosen by the
 * operator (robust to Clerk's auto-suffixed slugs). Only adopts a row still in
 * the 'pending:' state.
 */
export async function linkTenant(formData: FormData) {
  const { userId, orgId } = await auth();
  if (!userId || !orgId) redirect("/onboarding");
  const slug = String(formData.get("slug") || "");
  if (!slug) redirect("/onboarding");

  const row = await db.query.tenants.findFirst({ where: eq(tenants.slug, slug) });
  if (!row) redirect("/onboarding");
  if (!row.clerkOrgId.startsWith("pending:")) redirect("/dashboard"); // already claimed

  const client = await clerkClient();
  const org = await client.organizations.getOrganization({ organizationId: orgId });
  const [tenant] = await db
    .update(tenants)
    .set({ clerkOrgId: orgId, name: org.name })
    .where(and(eq(tenants.id, row.id), like(tenants.clerkOrgId, "pending:%")))
    .returning();
  if (tenant) await seedTenantChildren(tenant.id);
  redirect("/dashboard");
}

/** Slugify a Clerk org slug/name into a tenant slug matching tenants/<slug>/. */
function toSlug(input: string): string {
  return input
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/**
 * Provision the tenant row for the active Clerk org (idempotent). Seeds empty
 * integration rows + a settings row so the dashboard renders immediately.
 */
export async function provisionTenant() {
  const { userId, orgId } = await auth();
  if (!userId || !orgId) redirect("/onboarding");

  const existing = await db.query.tenants.findFirst({
    where: eq(tenants.clerkOrgId, orgId),
  });
  if (existing) redirect("/dashboard");

  const client = await clerkClient();
  const org = await client.organizations.getOrganization({ organizationId: orgId });
  const slug = toSlug(org.slug || org.name || orgId);

  // The local worker may have already seeded this tenant (clerk_org_id =
  // 'pending:<slug>'). Adopt that row — and its synced data — by linking it to
  // this Clerk org. Otherwise create a fresh row.
  const seeded = await db.query.tenants.findFirst({ where: eq(tenants.slug, slug) });
  let tenant;
  if (seeded && seeded.clerkOrgId.startsWith("pending:")) {
    [tenant] = await db
      .update(tenants)
      .set({ clerkOrgId: orgId, name: org.name })
      .where(eq(tenants.id, seeded.id))
      .returning();
  } else if (seeded) {
    // Already linked to another org — refuse to hijack.
    redirect("/dashboard");
  } else {
    [tenant] = await db
      .insert(tenants)
      .values({ clerkOrgId: orgId, slug, name: org.name })
      .returning();
  }

  await db
    .insert(integrations)
    .values(PROVIDERS.map((provider) => ({ tenantId: tenant.id, provider })))
    .onConflictDoNothing();
  await db.insert(settings).values({ tenantId: tenant.id }).onConflictDoNothing();

  redirect("/dashboard");
}
