"use server";

import { auth, clerkClient } from "@clerk/nextjs/server";
import { eq } from "drizzle-orm";
import { redirect } from "next/navigation";

import { db } from "@/lib/db";
import { integrations, settings, tenants } from "@/lib/db/schema";
import { PROVIDERS } from "@/lib/db/queries";

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

  const [tenant] = await db
    .insert(tenants)
    .values({ clerkOrgId: orgId, slug, name: org.name })
    .returning();

  await db
    .insert(integrations)
    .values(PROVIDERS.map((provider) => ({ tenantId: tenant.id, provider })))
    .onConflictDoNothing();
  await db.insert(settings).values({ tenantId: tenant.id }).onConflictDoNothing();

  redirect("/dashboard");
}
