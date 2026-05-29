"""Gemini AI client for Best Roadways — drafts email + WhatsApp copy.

Tenant-local. Reads GEMINI_API_KEY / GEMINI_MODEL from this tenant's .env.
The SDR loop uses this to generate hyper-personalised outreach that follows the
frameworks in strategy_playbook.md.

The Google key will be provided by the operator. Until then `draft()` raises a
clear error rather than failing obscurely.

Install:  pip install google-genai python-dotenv requests
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def _client():
    if not API_KEY:
        raise RuntimeError(
            "Gemini not configured. Set GEMINI_API_KEY in tenants/best-roadways/.env"
        )
    try:
        from google import genai
    except ImportError as e:
        raise RuntimeError(
            "google-genai not installed. Run: pip install google-genai"
        ) from e
    return genai.Client(api_key=API_KEY)


def draft(prompt, system=None, temperature=0.7):
    """Generate text from a prompt. `system` optionally sets persona/rules
    (e.g. the relevant section of strategy_playbook.md). Returns plain text."""
    client = _client()
    config = {"temperature": temperature}
    if system:
        config["system_instruction"] = system
    resp = client.models.generate_content(
        model=MODEL, contents=prompt, config=config
    )
    return (resp.text or "").strip()


if __name__ == "__main__":
    print("Gemini configured:", bool(API_KEY), "| model:", MODEL)
