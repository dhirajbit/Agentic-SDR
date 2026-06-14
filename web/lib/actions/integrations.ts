"use server";

import { auth } from "@clerk/nextjs/server";
import { and, eq } from "drizzle-orm";
import { revalidatePath } from "next/cache";

import { resolveTenant } from "@/lib/auth/tenant";
import { db } from "@/lib/db";
import { commands, integrations } from "@/lib/db/schema";
import {
  assertNoSecretLeak,
  CONFIG_FIELDS,
  SECRET_FIELDS,
  sealSecret,
} from "@/lib/crypto/seal";
import type { Provider } from "@/lib/db/queries";

/**
 * Save integration keys: seal each CHANGED secret to the tenant's public key,
 * store non-secret config in clear, then enqueue a test_connection command so
 * the worker decrypts, applies, health-checks, and writes status back.
 *
 * Secrets submitted blank/masked are left untouched (no clobber). A field set
 * to the literal "__REMOVE__" tombstone deletes that stored secret.
 */
export async function saveIntegration(provider: Provider, formData: FormData) {
  const { userId } = await auth();
  const tenant = await resolveTenant();
  if (!tenant.workerPublicKey) {
    throw new Error(
      "No worker public key yet — start the local worker once so it can publish its key.",
    );
  }

  const existing = await db.query.integrations.findFirst({
    where: and(eq(integrations.tenantId, tenant.id), eq(integrations.provider, provider)),
  });

  // Non-secret config (stored in clear).
  const config: Record<string, unknown> = { ...(existing?.config ?? {}) };
  for (const field of CONFIG_FIELDS[provider] ?? []) {
    const v = formData.get(field);
    if (typeof v === "string") config[field] = v;
  }
  assertNoSecretLeak(config);

  // Secrets (sealed). Skip blanks; honor the remove tombstone.
  const secretsCiphertext: Record<string, string> = { ...(existing?.secretsCiphertext ?? {}) };
  for (const field of SECRET_FIELDS[provider] ?? []) {
    const raw = formData.get(field);
    if (typeof raw !== "string") continue;
    const v = raw.trim();
    if (!v || v === "••••••••") continue; // unchanged / masked
    if (v === "__REMOVE__") {
      delete secretsCiphertext[field];
      continue;
    }
    secretsCiphertext[field] = await sealSecret(v, tenant.workerPublicKey);
  }

  await db
    .insert(integrations)
    .values({
      tenantId: tenant.id,
      provider,
      config,
      secretsCiphertext,
      status: "pending_test",
    })
    .onConflictDoUpdate({
      target: [integrations.tenantId, integrations.provider],
      set: { config, secretsCiphertext, status: "pending_test", updatedAt: new Date() },
    });

  await db.insert(commands).values({
    tenantId: tenant.id,
    type: "test_connection",
    args: { provider },
    requestedBy: userId ?? undefined,
  });

  revalidatePath("/dashboard/integrations");
  revalidatePath(`/dashboard/integrations/${provider}`);
}
