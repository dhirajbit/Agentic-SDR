"use client";

import { useEffect, useState, useTransition } from "react";

import { enqueueWhatsappLink } from "@/lib/actions/whatsapp";

type WaDetail = { session_status?: string; phone?: string; qr?: string; last_error?: string };

export function WhatsappLinker({
  initialStatus,
  initialDetail,
}: {
  initialStatus: string;
  initialDetail: WaDetail;
}) {
  const [status, setStatus] = useState(initialStatus);
  const [detail, setDetail] = useState<WaDetail>(initialDetail);
  const [pending, start] = useTransition();
  const [polling, setPolling] = useState(false);

  // Poll worker-written status while we're waiting for a scan / link.
  useEffect(() => {
    if (!polling) return;
    const id = setInterval(async () => {
      try {
        const res = await fetch("/api/integrations/whatsapp/status", { cache: "no-store" });
        if (!res.ok) return;
        const data = await res.json();
        setStatus(data.status);
        setDetail(data.detail ?? {});
        if (data.status === "connected") setPolling(false);
      } catch {
        /* ignore */
      }
    }, 2500);
    return () => clearInterval(id);
  }, [polling]);

  const connected = status === "connected" || detail.session_status === "ready";

  return (
    <div className="panel" style={{ marginTop: 20, display: "grid", gap: 16, maxWidth: 460 }}>
      {connected ? (
        <div>
          <div className="pill ok" style={{ width: "fit-content" }}>
            <span className="dot" /> linked
          </div>
          <p style={{ marginTop: 12 }}>
            WhatsApp connected{detail.phone ? ` — +${detail.phone}` : ""}. Inbound replies are
            ingested automatically via webhook.
          </p>
        </div>
      ) : (
        <>
          <p className="muted">
            Link a WhatsApp number through your local OpenWA gateway. Click connect, then scan the
            QR below in <strong>WhatsApp → Linked devices</strong>.
          </p>

          {detail.qr ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={detail.qr}
              alt="WhatsApp QR"
              width={260}
              height={260}
              style={{ borderRadius: 12, border: "1px solid var(--line)", background: "#fff" }}
            />
          ) : null}

          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button
              className="btn primary"
              disabled={pending}
              onClick={() =>
                start(async () => {
                  await enqueueWhatsappLink();
                  setPolling(true);
                })
              }
            >
              {pending ? "Requesting…" : detail.qr ? "Refresh QR" : "Connect WhatsApp"}
            </button>
            <span className="muted mono" style={{ fontSize: 12 }}>
              {polling
                ? `waiting for worker… (${detail.session_status ?? "starting"})`
                : detail.session_status
                  ? `status: ${detail.session_status}`
                  : "needs the local worker + OpenWA running"}
            </span>
          </div>
          {detail.last_error ? (
            <p className="pill warn" style={{ width: "fit-content" }}>
              {detail.last_error}
            </p>
          ) : null}
        </>
      )}
    </div>
  );
}
