"use server";

import { auth } from "@clerk/nextjs/server";
import { revalidatePath } from "next/cache";

import { resolveTenant } from "@/lib/auth/tenant";
import { db } from "@/lib/db";
import { commands, integrations } from "@/lib/db/schema";
import { and, eq } from "drizzle-orm";

/** Ask the local worker to create/start an OpenWA session and surface a QR. */
export async function enqueueWhatsappLink() {
  const { userId } = await auth();
  const tenant = await resolveTenant();
  // mark pending so the UI reflects "waiting for worker"
  await db
    .update(integrations)
    .set({ status: "pending_test", updatedAt: new Date() })
    .where(and(eq(integrations.tenantId, tenant.id), eq(integrations.provider, "whatsapp")));
  await db.insert(commands).values({
    tenantId: tenant.id,
    type: "whatsapp_link",
    requestedBy: userId ?? undefined,
  });
  revalidatePath("/dashboard/integrations/whatsapp");
}
