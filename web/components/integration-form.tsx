"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { saveIntegration } from "@/lib/actions/integrations";
import type { Provider } from "@/lib/db/queries";

export function IntegrationForm({
  provider,
  configFields,
  secretFields,
  config,
  hasSecret,
  workerReady,
}: {
  provider: Provider;
  configFields: string[];
  secretFields: string[];
  config: Record<string, string>;
  hasSecret: Record<string, boolean>;
  workerReady: boolean;
}) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [msg, setMsg] = useState<string | null>(null);

  function onSubmit(formData: FormData) {
    setMsg(null);
    start(async () => {
      try {
        await saveIntegration(provider, formData);
        setMsg("Saved. The worker will test the connection on its next loop.");
        router.refresh();
      } catch (e) {
        setMsg(e instanceof Error ? e.message : "Failed to save.");
      }
    });
  }

  return (
    <form action={onSubmit} className="panel" style={{ marginTop: 20, display: "grid", gap: 16 }}>
      {!workerReady ? (
        <p className="pill warn" style={{ width: "fit-content" }}>
          worker key not published yet — start the local worker once
        </p>
      ) : null}

      {configFields.map((field) => (
        <label key={field} style={{ display: "grid", gap: 6 }}>
          <span className="stat-label">{field}</span>
          <input
            name={field}
            defaultValue={config[field] ?? ""}
            className="mono"
            style={inputStyle}
            autoComplete="off"
          />
        </label>
      ))}

      {secretFields.map((field) => (
        <label key={field} style={{ display: "grid", gap: 6 }}>
          <span className="stat-label">
            {field} {hasSecret[field] ? <em className="muted">(stored — leave blank to keep)</em> : null}
          </span>
          <input
            name={field}
            type="password"
            placeholder={hasSecret[field] ? "••••••••" : ""}
            className="mono"
            style={inputStyle}
            autoComplete="new-password"
          />
          {hasSecret[field] ? (
            <button
              type="button"
              className="mono muted"
              style={{ justifySelf: "start", fontSize: 11, background: "none", border: "none", cursor: "pointer", padding: 0 }}
              onClick={(e) => {
                const input = (e.currentTarget.previousElementSibling as HTMLInputElement);
                input.value = "__REMOVE__";
                setMsg(`${field} will be removed on save.`);
              }}
            >
              remove stored key
            </button>
          ) : null}
        </label>
      ))}

      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <button className="btn primary" type="submit" disabled={pending || !workerReady}>
          {pending ? "Saving…" : "Save & test"}
        </button>
        {msg ? <span className="muted mono" style={{ fontSize: 12 }}>{msg}</span> : null}
      </div>
    </form>
  );
}

const inputStyle: React.CSSProperties = {
  padding: "9px 12px",
  border: "1px solid var(--line)",
  borderRadius: "var(--r-sm)",
  fontSize: 13,
  background: "var(--bg)",
};
