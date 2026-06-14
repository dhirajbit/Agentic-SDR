import Link from "next/link";
import { SignedIn, SignedOut } from "@clerk/nextjs";

export default function Home() {
  return (
    <main className="wrap" style={{ paddingTop: 80, maxWidth: 720 }}>
      <p className="mono stat-label">Agentic SDR</p>
      <h1 style={{ fontSize: 56, lineHeight: 1.05, marginTop: 12 }}>
        Meetings, booked on autopilot.
      </h1>
      <p className="muted" style={{ fontSize: 18, marginTop: 16 }}>
        Your SDR enriches, researches, writes, and sends across email and WhatsApp — then
        learns from every reply. This is the operator console: connect your tools, watch the
        loop, control the cycles.
      </p>
      <div style={{ display: "flex", gap: 12, marginTop: 28 }}>
        <SignedOut>
          <Link className="btn primary" href="/sign-in">
            Sign in
          </Link>
          <Link className="btn" href="/sign-up">
            Create account
          </Link>
        </SignedOut>
        <SignedIn>
          <Link className="btn primary" href="/onboarding">
            Open console
          </Link>
        </SignedIn>
      </div>
    </main>
  );
}
