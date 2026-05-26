# Agentic SDR

A plug-and-play AI-powered Sales Development Representative (SDR) toolkit. This repository contains all the necessary scripts, integrations, and instructions to run an autonomous, self-improving SDR agent out of the box for any company.

## 🚀 Overview

The Agentic SDR is not just a script; it's a dual-loop autonomous system powered by LLMs (Claude/Gemini):
1. **The SDR Loop:** Researches leads, crafts personalized emails and WhatsApp messages, logs activities to the CRM, and manages follow-ups.
2. **The Observer Loop:** Monitors campaign performance, delivery rates, and replies, updating the overall strategy in real-time.

It's designed to be completely generic—you just define what you're selling in a configuration file, and the agent adapts its pitch.

## 🗂 Project Structure

### Configuration
- **`company_config_template.json`**: Duplicate this to `company_config.json` and fill in your product details, value propositions, and sender info.
- **`qualification_rules_template.json`**: Duplicate this to `qualification_rules.json` to define what makes a lead "Qualified" (e.g., revenue minimums, industry keywords).
- **`.env.example`**: Duplicate to `.env` and provide your CRM and Email API keys.

### Core Automation Scripts
- **`crm_client.py`**: A generic CRM client for fetching, updating, and managing leads. (Defaulted to Frappe/ERPNext architecture, but adaptable).
- **`sync_leads.py`**: Pulls all lead data from your CRM into local JSON/CSV for offline AI processing.
- **`qualify_leads.py`**: Filters out junk and ranks leads based on your `qualification_rules.json`.
- **`merge_verdicts.py`**: Combines initial qualification with AI research outputs to create the final prioritized queue (`qualified_queue.json`).
- **`update_schedule.py`**: Manages the daily cadence and schedule limits (e.g., max 300 emails/day).
- **`generate_report.py`**: Creates a live HTML dashboard (`sdr_dashboard.html`) to visualize the AI's performance, open rates, and meetings booked.

### AI Prompts and Playbooks
- **`CLAUDE.md`**: The master instruction prompt for the AI agent running the loops.
- **`strategy_playbook_template.md`**: Duplicate to `strategy_playbook.md`. This is the living document the Observer loop updates with winning email strategies.

## 🛠 Setup Instructions

1. **Install Dependencies**
   ```bash
   pip install requests python-dotenv
   ```
2. **Configure Environment**
   - Copy `.env.example` to `.env` and fill in your API credentials.
3. **Configure the AI**
   - Copy `company_config_template.json` to `company_config.json` and describe your product.
   - Copy `qualification_rules_template.json` to `qualification_rules.json` and define your ideal customer profile.
   - Copy `strategy_playbook_template.md` to `strategy_playbook.md`.
4. **Sync Data**
   ```bash
   python sync_leads.py
   python qualify_leads.py
   python merge_verdicts.py
   ```
5. **Start the Agent**
   - Using an agentic CLI (like Claude Code or Gemini Agent), let it read `CLAUDE.md`.
   - The agent will use the `/loop` commands (e.g., `/loop 60m sdr-cycle`) to autonomously manage outreach.

## 📊 Dashboard

Run `python generate_report.py` anytime to generate a fresh `sdr_dashboard.html` that shows you everything the AI is doing, how campaigns are performing, and who is replying.
