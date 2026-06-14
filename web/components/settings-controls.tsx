"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { enqueueRun, updateSettings } from "@/lib/actions/commands";

export function SettingsControls({
  liveSend,
  autoLoop,
  canRun,
  driver,
}: {
  liveSend: boolean;
  autoLoop: boolean;
  canRun: boolean;
  driver: string;
}) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [live, setLive] = useState(liveSend);
  const [loop, setLoop] = useState(autoLoop);
  const [msg, setMsg] = useState<string | null>(null);

  const save = (next: { liveSend?: boolean; autoLoop?: boolean }) =>
    start(async () => {
      await updateSettings(next);
      setMsg("Saved.");
      router.refresh();
    });

  const run = (kind: "sdr" | "observer") =>
    start(async () => {
      try {
        await enqueueRun(kind);
        setMsg(`Queued ${kind} run for the worker.`);
        router.refresh();
      } catch (e) {
        setMsg(e instanceof Error ? e.message : "Failed.");
      }
    });

  return (
    <div className="panel" style={{ display: "grid", gap: 18 }}>
      <Toggle
        label="Live send"
        sub="Off = dry-run (drafts + logs, sends nothing)."
        checked={live}
        onChange={(v) => {
          setLive(v);
          save({ liveSend: v });
        }}
        disabled={pending}
      />
      <Toggle
        label="Auto-loop"
        sub="Worker runs SDR hourly + Observer every 3h within the send window."
        checked={loop}
        onChange={(v) => {
          setLoop(v);
          save({ autoLoop: v });
        }}
        disabled={pending}
      />

      <div style={{ borderTop: "1px solid var(--line)", paddingTop: 16 }}>
        {canRun ? (
          <div style={{ display: "flex", gap: 10 }}>
            <button className="btn primary" onClick={() => run("sdr")} disabled={pending}>
              Run SDR now
            </button>
            <button className="btn" onClick={() => run("observer")} disabled={pending}>
              Run Observer now
            </button>
          </div>
        ) : (
          <p className="muted mono" style={{ fontSize: 12 }}>
            This tenant is {driver}-driven; cycles run via its own loop, not Run-now.
          </p>
        )}
        {msg ? (
          <p className="muted mono" style={{ fontSize: 12, marginTop: 10 }}>
            {msg}
          </p>
        ) : null}
      </div>
    </div>
  );
}

function Toggle({
  label,
  sub,
  checked,
  onChange,
  disabled,
}: {
  label: string;
  sub: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <label style={{ display: "flex", alignItems: "center", gap: 14, cursor: "pointer" }}>
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        style={{ width: 18, height: 18 }}
      />
      <span>
        <div style={{ fontWeight: 600 }}>{label}</div>
        <div className="muted mono" style={{ fontSize: 11 }}>
          {sub}
        </div>
      </span>
      <span className={checked ? "pill ok" : "pill"} style={{ marginLeft: "auto" }}>
        {checked ? "on" : "off"}
      </span>
    </label>
  );
}
