"""Gemini-powered analysis of the Best Roadways qualified lead queue.

Builds a compact digest of the queue and asks Gemini for an ICP read: best-fit
freight segments, top accounts to hit first, and gaps. Used by the control panel
after a CSV upload.
"""

import json
from collections import Counter
from pathlib import Path

import gemini_client

TENANT_DIR = Path(__file__).resolve().parent
QUEUE = TENANT_DIR / "qualified_leads.json"
CONFIG = TENANT_DIR / "company_config.json"


def _digest(queue):
    titles = Counter((q.get("title") or "—") for q in queue)
    sizes = Counter((q.get("employees") or "—") for q in queue)
    channels = Counter((q.get("channel") or "—") for q in queue)
    cities = Counter((q.get("city") or "—") for q in queue)
    top = [
        {"company": q.get("company"), "title": q.get("title"),
         "city": q.get("city"), "score": q.get("priority_score")}
        for q in queue[:25]
    ]
    return {
        "total": len(queue),
        "by_title": dict(titles.most_common(10)),
        "by_size": dict(sizes.most_common()),
        "by_channel": dict(channels),
        "by_city": dict(cities.most_common(10)),
        "top_25_by_priority": top,
    }


def analyze_leads(queue=None):
    """Return a short markdown analysis of the queue, or a clear message if empty."""
    if queue is None:
        queue = json.loads(QUEUE.read_text()) if QUEUE.exists() else []
    if not queue:
        return "No qualified leads in the queue yet. Upload a CSV (or connect ERPNext) and re-run the pipeline."

    cfg = json.loads(CONFIG.read_text()) if CONFIG.exists() else {}
    digest = _digest(queue)

    system = (
        "You are the SDR strategist for Best Roadways Limited, India's trusted road-freight "
        "partner since 1985 (800+ owned GPS-tracked trucks, 65+ branches, 500+ cities; FTL, PTL, "
        "warehousing, chemical/hazmat, project & ODC cargo). You qualify SHIPPERS (FMCG, chemical, "
        "pharma, automotive, steel, etc.) who move physical goods — never other transporters/3PLs."
    )
    prompt = (
        "Here is a digest of the current qualified lead queue (JSON):\n\n"
        f"{json.dumps(digest, indent=2)}\n\n"
        "Company proof points: " + "; ".join(cfg.get("proof_points", [])) + "\n\n"
        "Give a concise analysis (markdown, ~150-220 words):\n"
        "1. Which freight segments in this list are the strongest fit and why.\n"
        "2. The 5-8 highest-priority accounts to contact first (from top_25_by_priority).\n"
        "3. Gaps / risks in the list (missing emails, thin titles, possible competitors to exclude).\n"
        "4. One sentence on email vs WhatsApp channel mix."
    )
    try:
        return gemini_client.draft(prompt, system=system, temperature=0.5)
    except Exception as e:
        return f"(Gemini analysis unavailable: {e})\n\nQueue digest:\n```json\n{json.dumps(digest, indent=2)}\n```"


if __name__ == "__main__":
    print(analyze_leads())
