import { NextResponse } from "next/server";
import { and, eq, lt } from "drizzle-orm";

import { db } from "@/lib/db";
import { commands } from "@/lib/db/schema";

/**
 * Vercel Cron: expire commands that have sat pending too long (worker offline).
 * Authenticated by the CRON_SECRET bearer token Vercel sends.
 */
export async function GET(req: Request) {
  const auth = req.headers.get("authorization");
  if (!process.env.CRON_SECRET || auth !== `Bearer ${process.env.CRON_SECRET}`) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const cutoff = new Date(Date.now() - 15 * 60 * 1000); // 15 min
  const expired = await db
    .update(commands)
    .set({ status: "expired", finishedAt: new Date(), result: { reason: "worker offline" } })
    .where(and(eq(commands.status, "pending"), lt(commands.createdAt, cutoff)))
    .returning({ id: commands.id });

  return NextResponse.json({ expired: expired.length });
}
