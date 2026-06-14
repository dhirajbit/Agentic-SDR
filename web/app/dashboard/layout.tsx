import Link from "next/link";
import { OrganizationSwitcher, UserButton } from "@clerk/nextjs";

import { resolveTenant } from "@/lib/auth/tenant";

const NAV = [
  { href: "/dashboard", label: "Overview" },
  { href: "/dashboard/integrations", label: "Integrations" },
  { href: "/dashboard/logs", label: "Logs" },
  { href: "/dashboard/cycles", label: "Cycles" },
  { href: "/dashboard/leads", label: "Leads" },
  { href: "/dashboard/settings", label: "Settings" },
];

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const tenant = await resolveTenant();
  return (
    <div>
      <header
        style={{
          borderBottom: "1px solid var(--line)",
          background: "var(--surface)",
          position: "sticky",
          top: 0,
          zIndex: 10,
        }}
      >
        <div
          className="wrap"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 20,
            paddingTop: 12,
            paddingBottom: 12,
          }}
        >
          <Link href="/dashboard" style={{ fontFamily: "var(--font-display)", fontWeight: 900 }}>
            SDR Console
          </Link>
          <span className="pill mono">{tenant.slug}</span>
          <nav style={{ display: "flex", gap: 14, marginLeft: 12, flexWrap: "wrap" }}>
            {NAV.map((n) => (
              <Link key={n.href} href={n.href} className="mono" style={{ fontSize: 13 }}>
                {n.label}
              </Link>
            ))}
          </nav>
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 12 }}>
            <OrganizationSwitcher hidePersonal afterSelectOrganizationUrl="/dashboard" />
            <UserButton />
          </div>
        </div>
      </header>
      <main className="wrap">{children}</main>
    </div>
  );
}
