"""Gemini AI client for Abhiyanta Tech — drafts SAP outreach copy.

Tenant-local. Reads GEMINI_API_KEY / GEMINI_MODEL from this tenant's .env.
The SDR cycle uses this to draft hyper-personalised email following the
frameworks in strategy_playbook.md.

Install:  pip install google-genai
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def _client():
    if not API_KEY:
        raise RuntimeError("Gemini not configured. Set GEMINI_API_KEY in tenants/abhiyanta-tech/.env")
    try:
        from google import genai
    except ImportError as e:
        raise RuntimeError("google-genai not installed. Run: pip install google-genai") from e
    return genai.Client(api_key=API_KEY)


def draft(prompt, system=None, temperature=0.7):
    """Generate text from a prompt. `system` optionally sets persona/rules
    (e.g. the relevant section of strategy_playbook.md). Returns plain text."""
    client = _client()
    config = {"temperature": temperature}
    if system:
        config["system_instruction"] = system
    resp = client.models.generate_content(model=MODEL, contents=prompt, config=config)
    return (resp.text or "").strip()


if __name__ == "__main__":
    print("Gemini configured:", bool(API_KEY), "| model:", MODEL)
