"use server";

import { auth } from "@clerk/nextjs/server";
import { eq } from "drizzle-orm";
import { revalidatePath } from "next/cache";

import { resolveTenant } from "@/lib/auth/tenant";
import { db } from "@/lib/db";
import { commands, settings } from "@/lib/db/schema";

/** Enqueue a cycle run for the local worker to claim. */
export async function enqueueRun(kind: "sdr" | "observer", args: Record<string, unknown> = {}) {
  const { userId } = await auth();
  const tenant = await resolveTenant();
  if (tenant.driver !== "sdr_cycle") {
    throw new Error("Run-now is only available for sdr_cycle tenants.");
  }
  await db.insert(commands).values({
    tenantId: tenant.id,
    type: kind === "sdr" ? "run_sdr" : "run_observer",
    args,
    requestedBy: userId ?? undefined,
  });
  revalidatePath("/dashboard");
  revalidatePath("/dashboard/cycles");
}

/** Persist a settings toggle and enqueue an apply_settings command for the worker. */
export async function updateSettings(form: { liveSend?: boolean; autoLoop?: boolean }) {
  const { userId } = await auth();
  const tenant = await resolveTenant();

  await db
    .insert(settings)
    .values({
      tenantId: tenant.id,
      liveSend: form.liveSend ?? false,
      autoLoop: form.autoLoop ?? false,
      updatedBy: userId ?? undefined,
    })
    .onConflictDoUpdate({
      target: settings.tenantId,
      set: {
        ...(form.liveSend !== undefined ? { liveSend: form.liveSend } : {}),
        ...(form.autoLoop !== undefined ? { autoLoop: form.autoLoop } : {}),
        updatedAt: new Date(),
        updatedBy: userId ?? undefined,
      },
    });

  const current = await db.query.settings.findFirst({ where: eq(settings.tenantId, tenant.id) });
  await db.insert(commands).values({
    tenantId: tenant.id,
    type: "apply_settings",
    args: { liveSend: current?.liveSend, autoLoop: current?.autoLoop },
    requestedBy: userId ?? undefined,
  });
  revalidatePath("/dashboard/settings");
}
