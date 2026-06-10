# Design System — Agentic SDR Landing Page

> Working name: **placeholder** ("Autopilot" used as a swappable wordmark — no product name chosen yet).
> Live prototype: `landing/index.html` (self-contained, open in any browser).

## Product Context
- **What this is:** An autonomous AI inside-sales rep. It ingests leads from any source, enriches and researches each one, decides the strategy and cadence itself, reaches out over email + WhatsApp + phone, books the meeting, and rewrites its own playbook from every reply.
- **Who it's for:** B2B founders, sales leaders and RevOps — buyers who've seen Artisan/11x and are skeptical of AI slop. India-first (WhatsApp is first-class).
- **Space/peers:** AI SDR / sales automation — Artisan (Ava), 11x (Alice), AiSDR, Clay, Apollo.
- **Project type:** Customer-facing marketing landing page (animation-forward).
- **Grounded in:** `kstars-sdr` (the Bolti run) and this repo's `CLAUDE.md` / playbook. Real numbers and sample emails come from those.

## Aesthetic Direction
- **Direction:** "Operator's Console" — a warm dark instrument panel that feels like a precision system running quietly, not a chatbot toy.
- **Decoration level:** intentional — faint dot-grid, subtle grain, one signature living element (the flow loop).
- **Mood:** calm + engineered + quietly alive. First-3-seconds reaction target: "this is under control," not "another spray cannon."
- **Differentiation vs category:** the **loop is the hero** (not an AI mascot/persona), **monospace telemetry** is a core voice, and **guardrails are sold as features**. The opposite of category convention, aimed at the skeptical operator.
- **Reference:** https://www.artisan.co/ai-sales-agent (dark premium, persona-led — we deliberately diverge on persona).

## Typography  *(revised 2026-06-09)*
- **Display + Body:** Perfectly Nineties (400–900) — editorial nineties character, self-hosted from `landing/perfectly-nineties-font-family-1780968794-0/*.otf`. Serif fallbacks (`Times New Roman`, Georgia).
- **Telemetry/Data:** Geist Mono — the signature move. Every "system of record" element (activity feed, timestamps, the strategy/suggestion card) renders in mono. *Loaded via Google Fonts.*
- **Loading:** local `@font-face` (Perfectly Nineties) + Google Fonts (Geist Mono).
- **Scale:** H1 clamp(40→76px) wght 900; H2 clamp(30→50px); H3 20–26px; body 16–20px; mono 11–13px.

## Color  *(revised 2026-06-09 — "bright but disciplined")*
- **Approach:** bright, restrained, one accent + one support. Signal-based.
- **Surfaces (light/paper):** bg `#FBFAF6` (warm paper) → surface `#FFFFFF` → elevated `#F3F1EA`; lines `#E4E0D6` / `#EDEAE2`.
- **Text:** `#16140F` ink · `#6B6658` muted · `#A8A293` faint.
- **Primary — electric green `#00C98A`** (dim `#009E6C`): alive / qualified / booked / healthy pipeline.
- **Support — coral `#FF5A3C`** (dim `#D63C20`): WhatsApp + replies + human-in-loop + urgent follow-ups.
- **Tertiary (quiet) — slate `#5E6B73`:** voice/call channel only, deliberately desaturated so it never competes.
- **Deliberately avoided:** cyan (Artisan owns it), **purple/violet/indigo and any blue→purple gradient (AI-slop pattern #1)**, more than 2 loud accents, 3-colour gradients.
- **Mode:** light/bright in v1 (was dark "Operator's Console" — pivoted per operator request for bright + futuristic, then disciplined down to kill slop).

## Spacing
- **Base unit:** 8px.
- **Density:** spacious for the marketing narrative, compact for product/telemetry panels.
- **Scale:** 8 / 16 / 24 / 32 / 48 / 64 / 96 / 128. Max content width 1180px.

## Layout
- **Approach:** hybrid — editorial/asymmetric for narrative, grid-disciplined for product panels.
- **First viewport = poster:** one headline + the living flow diagram, not a document.
- **Border radius:** sm 9px · md 14px · lg 18px · pill 20px.

## Motion  *(revised 2026-06-10)*
- **Approach:** intentional → expressive (animation is a stated requirement).
- **Signatures:**
  1. **Hero flow** — four stages (Source → Research → Reach → Booked) light left-to-right with arrow connectors; "↺ learns from every reply" loop-back pill.
  2. **Horizontal orchestration strip** — company spotted → researched (notes pop) → email drafts live (typewriter) → sent ✓ → WhatsApp follow-up + reply bubble → meeting booked. Progress bar tracks the sequence; loops; horizontal scroll-snap on mobile.
  3. **Learning card** — email draft types in real time while "learned from past replies" lines pop at the exact phrase they influenced.
  4. **CRM sync feed** — mono ticker: action → logged to Zoho/Kylas/HubSpot/… ✓ with real favicons.
  5. **Live activity feed** + count-up stats + reply-source bars on scroll.
- **Easing:** `cubic-bezier(.22,.61,.36,1)`. Durations: micro 150ms, short 250–400ms, long 700ms+. Typewriters ~25ms/2 chars.
- **Accessibility:** full `prefers-reduced-motion` fallback (final states shown, no animation).

## Logo Strategy  *(revised 2026-06-10)*
- **Brand logos:** real, colored, via Google favicon service (`google.com/s2/favicons?domain=<domain>&sz=64`), keyed by domain (`<img data-logo="zoho.com">`), dot fallback on failure. Switched from Simple Icons because LinkedIn/Salesforce were removed from that CDN (blank icons in production).
- **Used:** Zoho, Kylas, Freshworks, HubSpot, Salesforce, ERPNext, WhatsApp, Gmail, Outlook, Google Calendar, LinkedIn, Calendly.
- **Placeholder slots:** dashed-border chips (`.logo.ph`) for **trademarked customer logos** (Tata/Nelco, Wow! Momo, Nilons, Everest Group, Best Roadways). Swap in real SVGs with permission before publishing.

## Page Sections (11)
1. Nav (placeholder wordmark + CTAs) · 2. Hero + animated flow · 3. Ingest logo marquee ·
4. The agent decides (strategy/cadence) · 5. Multi-channel cadence timeline ·
6. The dual loop (Observer rewrites playbook, real win-rates) · 7. Discipline = feature ·
8. Live dashboard · 9. The writing (verbatim emails + rules) · 10. Proof wall (metrics + customer placeholders) ·
11. FAQ · Final CTA + footer.

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-06-08 | Initial design system + runnable prototype | Created by /design-consultation. "Operator's Console" dark, signal-green+amber, loop-as-hero, mono telemetry. Grounded in kstars-sdr (Bolti) capabilities and real metrics. |
| 2026-06-08 | Loop is hero, not an AI persona | Category sells mascots (Ava/Alice); this product's moat is the self-improving closed loop + logging discipline. Credibility wins with skeptical operators. |
| 2026-06-08 | Guardrails sold as features | Credit gate, send windows, caps, opt-outs reframed as trust signals — the opposite of the category, which hides limits. |
| 2026-06-09 | Messaging pivot: outcomes over process | Hero leads "meetings booked on autopilot"; WhatsApp 50× wedge, replace-payroll, orchestration animation added; framework names / credit-gate / dual-loop internals stripped from the public page (still in the product). Sections reworked from the original 11. |
| 2026-06-09 | Type pivot: Perfectly Nineties | Operator asked for a nineties character. Replaced Cabinet Grotesk/Geist with self-hosted Perfectly Nineties for display + body; Geist Mono retained for telemetry. |
| 2026-06-09 | Color pivot: bright, then disciplined | Operator asked for "bright + futuristic." First pass went light-lavender + violet/pink/mint with 3-colour gradients — tripped AI-slop pattern #1 (purple gradients) and contradicted the dark-native call. Corrected to warm-paper + one electric-green accent + coral support, violet removed entirely. /design-review, operator chose "bright but disciplined." |
| 2026-06-10 | De-slop pass 2 (operator screenshots) | Killed gradient text (hero + 50× now solid), removed pink section washes, fixed hero flow (Source→Research→Reach→Booked, arrow connectors, no broken arc/pulse). Orchestration rebuilt horizontal with live email typewriter; new learning card (draft types while past-win tags pop); new CRM sync section (Zoho/Kylas/Freshworks/HubSpot/Salesforce/ERPNext). Logos switched to real colored favicons by domain — Simple Icons had dropped LinkedIn/Salesforce. |
