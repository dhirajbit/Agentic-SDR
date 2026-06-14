import { NextResponse } from "next/server";

import { resolveTenant } from "@/lib/auth/tenant";
import { getCycleRun } from "@/lib/db/queries";

export async function GET(_req: Request, { params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  const tenant = await resolveTenant(); // enforces tenant scope via Clerk session
  const run = await getCycleRun(tenant.id, runId);
  if (!run) return NextResponse.json({ error: "not found" }, { status: 404 });
  return NextResponse.json({ status: run.status, log: run.log ?? "" });
}
