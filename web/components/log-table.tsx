"use client";

import { useState } from "react";

import { StatusPill } from "@/components/ui";

export type LogRow = {
  id: string;
  occurredAt: string;
  channel: string;
  campaign: string | null;
  company: string | null;
  recipient: string | null;
  framework: string | null;
  subject: string | null;
  body: string | null;
  status: string | null;
};

export function LogTable({ rows }: { rows: LogRow[] }) {
  const [open, setOpen] = useState<string | null>(null);

  if (rows.length === 0) {
    return <p className="muted" style={{ padding: 12 }}>No actions yet.</p>;
  }

  return (
    <table className="feed">
      <thead>
        <tr>
          <th>When</th>
          <th>Channel</th>
          <th>Campaign</th>
          <th>Company</th>
          <th>Recipient</th>
          <th>Framework</th>
          <th>Subject / message</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((a) => {
          const isOpen = open === a.id;
          return (
            <>
              <tr key={a.id}>
                <td className="mono" style={{ whiteSpace: "nowrap" }}>
                  {new Date(a.occurredAt).toLocaleDateString()}
                </td>
                <td>
                  {/* Click the channel badge to expand the full email/message. */}
                  <button
                    type="button"
                    onClick={() => setOpen(isOpen ? null : a.id)}
                    className={a.channel === "whatsapp" ? "pill warn" : "pill"}
                    style={{ cursor: "pointer", border: "1px solid var(--line)" }}
                    title="Show full message"
                  >
                    {a.channel} {isOpen ? "▾" : "▸"}
                  </button>
                </td>
                <td style={{ whiteSpace: "nowrap" }}>
                  {a.campaign ? <span className="pill">{a.campaign}</span> : <span className="muted">—</span>}
                </td>
                <td>{a.company}</td>
                <td className="mono">{a.recipient}</td>
                <td>{a.framework}</td>
                <td style={{ maxWidth: 340 }}>{a.subject || a.body?.slice(0, 80)}</td>
                <td>{a.status ? <StatusPill status={a.status} /> : null}</td>
              </tr>
              {isOpen ? (
                <tr key={`${a.id}-detail`}>
                  <td colSpan={8} style={{ background: "var(--elevated)" }}>
                    <div style={{ padding: "8px 4px", maxWidth: 760 }}>
                      <div className="stat-label">To</div>
                      <div className="mono" style={{ marginBottom: 8 }}>
                        {a.recipient} {a.company ? `· ${a.company}` : ""}
                      </div>
                      <div className="stat-label">Subject</div>
                      <div style={{ fontWeight: 600, marginBottom: 8 }}>{a.subject}</div>
                      <div className="stat-label">Body</div>
                      <pre
                        style={{
                          whiteSpace: "pre-wrap",
                          fontFamily: "inherit",
                          margin: "4px 0 0",
                          lineHeight: 1.5,
                        }}
                      >
                        {a.body || "(no body)"}
                      </pre>
                    </div>
                  </td>
                </tr>
              ) : null}
            </>
          );
        })}
      </tbody>
    </table>
  );
}
