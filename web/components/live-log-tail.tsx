"use client";

import { useEffect, useRef, useState } from "react";

/** Polls a running cycle's log every 3s until it's no longer running. */
export function LiveLogTail({ runId, initialLog }: { runId: string; initialLog: string }) {
  const [log, setLog] = useState(initialLog);
  const [status, setStatus] = useState("running");
  const boxRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const res = await fetch(`/api/cycles/${runId}/log`, { cache: "no-store" });
        if (!res.ok) return;
        const data = await res.json();
        if (!alive) return;
        setLog(data.log ?? "");
        setStatus(data.status ?? "running");
      } catch {
        /* ignore transient errors */
      }
    };
    const id = setInterval(() => {
      if (status === "running" || status === "pending") tick();
    }, 3000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [runId, status]);

  useEffect(() => {
    boxRef.current?.scrollTo(0, boxRef.current.scrollHeight);
  }, [log]);

  return (
    <pre ref={boxRef} className="logbox" style={{ marginTop: 12 }}>
      {log || "(waiting for output…)"}
    </pre>
  );
}
