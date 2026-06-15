"""Local worker daemon: bridges one tenant's local SDR to the hosted Neon DB.

Single-tenant, scoped by AGENTIC_SDR_TENANT (same convention as the rest of the
repo). Run one process per tenant:

    AGENTIC_SDR_TENANT=best-roadways python cloud_agent.py

It (1) publishes the tenant's worker public key, (2) heartbeats, (3) claims and
executes commands from the web (apply secrets / test connection / run cycle /
apply settings), and (4) periodically pushes tracker/leads/integration health.

Cycles only run for driver='sdr_cycle' tenants (best-roadways). Claude-driven
tenants (abhiyanta) push state only; run-cycle commands are rejected.
"""

import importlib
import json
import os
import sys
import time
import traceback
from pathlib import Path

from dotenv import load_dotenv

import cloud_sync

REPO_ROOT = Path(__file__).resolve().parent
SLUG = os.getenv("AGENTIC_SDR_TENANT")
if not SLUG:
    raise SystemExit("AGENTIC_SDR_TENANT not set.")
TENANT_DIR = REPO_ROOT / "tenants" / SLUG
load_dotenv(TENANT_DIR / ".env")

LOOP_SECONDS = int(os.getenv("CLOUD_AGENT_LOOP_SECONDS", "10"))
PUSH_EVERY = int(os.getenv("CLOUD_AGENT_PUSH_EVERY", "6"))  # loops between passive pushes
DRIVER = os.getenv("SDR_DRIVER", "sdr_cycle")


def log(msg: str) -> None:
    print(f"[cloud-agent:{SLUG}] {msg}", flush=True)


def tenant_name() -> str:
    cfg = TENANT_DIR / "company_config.json"
    if cfg.exists():
        try:
            return json.loads(cfg.read_text()).get("company_name") or SLUG
        except Exception:  # noqa: BLE001
            pass
    return SLUG


# --------------------------------------------------------------------------- #
# Health checks — lazy import + reload so freshly-applied .env keys are seen.
# Each returns (status, detail_dict). Never raises.
# --------------------------------------------------------------------------- #

def _reload(modname: str, path: Path | None = None):
    if path and str(path) not in sys.path:
        sys.path.insert(0, str(path))
    if modname in sys.modules:
        return importlib.reload(sys.modules[modname])
    return importlib.import_module(modname)


def check_apollo():
    m = _reload("apollo_client")
    bal = m.get_credit_balance()
    return "connected", {"credits_left": bal["lead_credit"]["left_over"]}


def check_whatsapp():
    m = _reload("openwa_client")
    s = m.get_session_status()
    status = "connected" if s.get("status") == "ready" else "error"
    return status, {"session_status": s.get("status"), "phone": s.get("phone")}


def check_brevo():
    m = _reload("brevo_client", TENANT_DIR)
    m.get_events(limit=1)
    return "connected", {"sender": getattr(m, "SENDER_EMAIL", None)}


def check_erpnext():
    m = _reload("erpnext_client", TENANT_DIR)
    n = m.get_lead_count() if hasattr(m, "get_lead_count") else len(m.get_leads(limit=1))
    return "connected", {"leads": n}


def check_gemini():
    m = _reload("gemini_client", TENANT_DIR)
    m.draft("ping", system="Reply OK.", temperature=0)
    return "connected", {"model": getattr(m, "MODEL", None)}


def check_zoho():
    mcp = TENANT_DIR / ".mcp.json"
    if not mcp.exists():
        return "unconfigured", {}
    data = json.loads(mcp.read_text())
    ok = any("zoho" in k.lower() for k in data.get("mcpServers", {}))
    return ("connected" if ok else "unconfigured"), {}


CHECKERS = {
    "apollo": check_apollo,
    "whatsapp": check_whatsapp,
    "brevo": check_brevo,
    "erpnext": check_erpnext,
    "gemini": check_gemini,
    "zoho": check_zoho,
}


def refresh_health(only: str | None = None) -> None:
    """Run health checks and push non-secret status. `only` limits to one provider."""
    providers = [only] if only else list(CHECKERS)
    for provider in providers:
        checker = CHECKERS.get(provider)
        if not checker:
            continue
        try:
            status, detail = checker()
        except Exception as exc:  # noqa: BLE001
            status, detail = "error", {"last_error": str(exc)[:200]}
        cloud_sync.push_integration_status(SLUG, provider, status, detail)


# --------------------------------------------------------------------------- #
# Cycle execution (sdr_cycle tenants only)
# --------------------------------------------------------------------------- #

def _tail_since(path: Path, start: int) -> str:
    if not path.exists():
        return ""
    with open(path) as f:
        f.seek(start)
        return f.read()


def run_cycle(kind: str, args: dict, command_id: str) -> dict:
    driver = os.getenv("SDR_DRIVER", "sdr_cycle")
    if driver != "sdr_cycle":
        raise RuntimeError(f"Run-{kind} unsupported for driver={driver}.")
    sys.path.insert(0, str(TENANT_DIR))
    sdr_cycle = _reload("sdr_cycle", TENANT_DIR)

    run_id = cloud_sync.push_cycle_run(SLUG, kind, "running", trigger="manual",
                                       command_id=command_id)
    cycle_log = TENANT_DIR / "cycle.log"
    start = cycle_log.stat().st_size if cycle_log.exists() else 0
    try:
        settings = cloud_sync.get_settings(SLUG)
        if kind == "sdr":
            summary = sdr_cycle.run_sdr_cycle(
                live_send=settings["live_send"], limit=args.get("limit")
            )
        else:
            summary = sdr_cycle.run_observer_cycle()
        log_body = _tail_since(cycle_log, start)
        cloud_sync.push_cycle_run(SLUG, kind, "done", run_id=run_id,
                                  summary=summary, log=log_body)
        cloud_sync.push_tracker(SLUG)
        cloud_sync.push_leads_counts(SLUG)
        return {"run_id": run_id, "summary": summary}
    except Exception as exc:  # noqa: BLE001
        log_body = _tail_since(cycle_log, start) + f"\nERROR: {exc}\n{traceback.format_exc()}"
        cloud_sync.push_cycle_run(SLUG, kind, "error", run_id=run_id, log=log_body)
        raise


# --------------------------------------------------------------------------- #
# Command dispatch
# --------------------------------------------------------------------------- #

def dispatch(cmd: dict) -> None:
    ctype, args, cid = cmd["type"], cmd.get("args", {}), cmd["id"]
    log(f"command {ctype} {args}")
    try:
        if ctype in ("apply_secrets", "test_connection"):
            decrypted = cloud_sync.pull_integration_secrets(SLUG)
            cloud_sync.apply_secrets_to_env(SLUG, decrypted)
            refresh_health(only=args.get("provider"))
            cloud_sync.complete_command(cid, "done")
        elif ctype == "apply_settings":
            (TENANT_DIR / "panel_settings.json").write_text(
                json.dumps(
                    {"live_send": bool(args.get("liveSend")), "auto_loop": bool(args.get("autoLoop"))},
                    indent=2,
                )
            )
            cloud_sync.complete_command(cid, "done")
        elif ctype == "run_sdr":
            cloud_sync.complete_command(cid, "done", run_cycle("sdr", args, cid))
        elif ctype == "run_observer":
            cloud_sync.complete_command(cid, "done", run_cycle("observer", args, cid))
        else:
            cloud_sync.complete_command(cid, "error", {"error": f"unknown type {ctype}"})
    except Exception as exc:  # noqa: BLE001
        log(f"command {ctype} failed: {exc}")
        cloud_sync.complete_command(cid, "error", {"error": str(exc)[:300]})


def main() -> None:
    log(f"starting (loop={LOOP_SECONDS}s, driver={DRIVER}, db={'set' if cloud_sync.DB_URL else 'MISSING'})")
    cloud_sync.ensure_tenant(SLUG, tenant_name(), DRIVER)
    published = False
    i = 0
    while True:
        try:
            if not published:
                if cloud_sync.publish_public_key(SLUG):
                    published = True
                    log("published worker public key")
                else:
                    log(f"tenant '{SLUG}' not provisioned in web yet — waiting")
            cloud_sync.heartbeat(SLUG)

            cmd = cloud_sync.claim_command(SLUG)
            while cmd:
                dispatch(cmd)
                cmd = cloud_sync.claim_command(SLUG)

            if i % PUSH_EVERY == 0:
                cloud_sync.push_tracker(SLUG)
                cloud_sync.push_leads_counts(SLUG)
                refresh_health()
        except Exception as exc:  # noqa: BLE001 — keep the daemon alive
            log(f"loop error: {exc}")
        i += 1
        time.sleep(LOOP_SECONDS)


if __name__ == "__main__":
    main()
