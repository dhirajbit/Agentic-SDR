# Strategy Playbook: Best Roadways Limited

Source of truth for all SDR outbound for Best Roadways. The SDR loop reads this before drafting any message. The Observer loop updates it based on reply/open data.

**Email frameworks ported from the Bolti playbook. WhatsApp cadence ported from the kstars-sdr model.** Both are kept verbatim in structure; only the value prop and example copy are re-anchored to road freight.

---

## Core Value Proposition

> Best Roadways is India's most trusted road-freight partner since 1985 — 800+ **owned** GPS-tracked, BS-VI vehicles, 65+ branches, 500+ cities, with own port infrastructure at Nhava Sheva. We move FMCG, chemical, pharma, automotive, steel and project cargo reliably, on time, on dedicated lanes.

### What makes us different
- **Owned fleet, not brokered** — 800+ company-owned trucks, all GPS-tracked and BS-VI compliant. Predictable transit, real-time visibility, no last-minute "no truck" surprises.
- **40 years, 65+ branches, 500+ cities** — owned hubs and dedicated lanes (esp. the Mumbai–Delhi corridor where we are the largest mover).
- **Chemical / hazmat depth** — PESO-certified tankers and lined containers; the first call for major chemical companies in the Gujarat belt.
- **End-to-end** — FTL, PTL, bonded warehousing (75,000 sq ft at Nhava Sheva), CFS/container handling, and project & ODC cargo under one roof.

### Key proof points
- Transport Ratna (2015) + Transport Samrat (2018) from AIMTC.
- Own warehouse, weighbridge and truck terminal at Nhava Sheva / JNPT.
- 40+ years serving FMCG, chemical, pharma, automotive shippers.

---

## Industry & Role Targeting

We sell freight **to shippers** (companies that move physical goods). We do **not** target other transporters / 3PLs / forwarders — they are competitors.

### Target 1: Chemical / Petrochemical (highest fit)
- **Ideal titles:** Logistics Head, Supply Chain Head, Plant Head, Procurement Head, Ops Head, COO.
- **Pain points:** Hazmat compliance, tanker availability, Gujarat-belt dispatch reliability, PESO paperwork.
- **Hook:** "Curious how you're handling tanker availability out of the Gujarat belt right now."
- **Framework:** Vanilla Ice Cream (lead with PESO-certified owned tankers).

### Target 2: FMCG / Consumer Goods / Pharma
- **Ideal titles:** Head of Logistics, Supply Chain Head, Distribution Head, VP Operations.
- **Pain points:** Peak-season capacity crunch, multi-region distribution, transit-time consistency, damage/visibility.
- **Hook:** "Saw [Company] is expanding distribution into [region] — how's transporter capacity holding up?"
- **Framework:** Mouse Trap.

### Target 3: Automotive / Steel / Engineering / Project cargo
- **Ideal titles:** Plant Head, Logistics Head, Procurement Head, Materials Head.
- **Pain points:** ODC/project movement, JIT inbound, line-stoppage risk from late freight.
- **Hook:** "How are you moving ODC consignments to [site] today — own fleet or spot market?"
- **Framework:** Vanilla Ice Cream / Mouse Trap.

---

## Email Frameworks (approved — ported from Bolti)

### 1. Vanilla Ice Cream (VIC) — DEFAULT first touch
> **Structure (40–55 words):** [Personalised observation about their company] → [freight/supply-chain pain] → [credibility / customer-type proof] → [what Best Roadways does, 1 line] → [soft ask].
> **Example:** "Saw [Company] runs a lot of chemical movement out of Gujarat. Tanker availability there gets tight fast. We run 800+ owned PESO-certified vehicles on those lanes for a few chemical firms. Worth a quick chat on your peak-season capacity?"

**VIC is the proven winner (≈44% open rate in the source program). Use it for first touches by default.**

### 2. Mouse Trap (observation + binary question)
> **Structure:** [Personalised observation / recent news] → [binary problem question implying we solve it].
> **Example:** "Noticed [Company] is scaling distribution into North India — curious if your current transporter is keeping FTL transit times consistent on the Mumbai–Delhi lane, or is that still a headache?"
> Use for short follow-ups; thinner than VIC for a first touch.

### 3. Neutral Insight (follow-up 1)
> **Structure:** [freight industry trend — BS-VI/GPS mandates, fuel/route shifts, festive-season capacity] → [how it affects them] → [soft ask].
> Performs ~2x better on warm leads (those who opened the first touch).

### 4. Thoughtful Bump (follow-up 2)
> "Any thoughts on the note above? Happy to ghost if freight isn't a priority right now."

### 5. Breakup (final touch)
> "Reached out a couple times about freight capacity for [Company]. Guessing timing's off — totally get it. If it becomes relevant, happy to chat. Closing the loop for now."

---

## Rules (Do NOT violate)

- **Length:** First touches under 50 words (VIC may run 40–55). 3rd–5th-grade reading level — simple words, short sentences.
- **Tone:** Casual, human, slightly unsure ("Not sure if this is relevant…", "Curious if…"). Humble/unsure copy outperforms confident claims. Never "I hope this email finds you well."
- **Customer-centric:** Talk about THEIR freight problem, not our feature list. Goal = get a reply, not book a meeting.
- **Subject lines:** 4–8 words, include the company name (every open in the source data had it). Hint at value. Examples: "tanker capacity for [Company]", "[Company] Mumbai–Delhi freight", "owned-fleet option for [Company]".
- **CTA:** Soft question ("Worth a quick chat?", "Open to a call?"). Never "Tuesday 3 PM" in a cold first touch.
- **Never name competitors** (other transporters / 3PLs) — even to differentiate.
- **Max one follow-up per lead** (source program policy). Don't over-sequence.
- **Never reuse the same template** for two people at the same company.

### Banned phrases
- "I hope this email finds you well"
- "I would love to explore the possibility of perhaps scheduling…"
- Kitchen-sink feature dumps / capability lists
- Deceptive subject lines
- Assumed pain ("You definitely need…") — ask, don't tell.

---

## WhatsApp Cadence (ported from kstars-sdr)

WhatsApp is the **48-hour follow-up channel** after the first email, only for leads that have a `mobile_no`.

- **Trigger:** 48h after the first email send, if no reply yet and the lead has a mobile number.
- **Identity:** First name only — "Hi [First Name], this is [Sender] from Best Roadways."
- **Style:** 2–4 sentences, casual, natural Hindi-English mix if the lead is Indian. No "Dear Sir/Madam", no corporate speak. One question at a time. Be helpful, not pushy.
- **Reference the company heavily** for no-first-name / bulk-imported leads (use `company_name`).

### Pacing & safety (hard rules)
- **Hard cap: 10 WhatsApp sends/day.**
- **Warm-up ramp:** Mon = 5, Tue = 7, Wed onward = up to 10/day.
- **90–120 seconds between sends.**
- **Abort the whole batch on the first "Not connected" error** from the bridge (re-auth the QR, then resume).
- **Rotate 4 templates** (below) — never send the same wording twice in a batch.

### WhatsApp templates (rotate)
1. "Hi [First Name], this is [Sender] from Best Roadways. Saw [Company] moves a fair bit of freight — we run 800+ owned GPS-tracked trucks across 500+ cities. Worth a quick chat on your lanes?"
2. "Hey [First Name], [Sender] here (Best Roadways). Just following up on my email about FTL/PTL capacity for [Company]. Happy to share rates for your key lanes if useful?"
3. "Hi [First Name] — quick one. Is [Company]'s transporter capacity holding up this season? We've got owned-fleet headroom on the [region] lanes. Open to a call?"
4. "Hello [First Name], [Sender] from Best Roadways. We handle chemical/FMCG freight PAN-India on dedicated lanes. Thought it might be relevant for [Company] — worth 10 mins?"

### Opt-out handling
- If a lead says not interested (email or WhatsApp): add them to `blocked_leads.json`, log "OPTED OUT" to the ERPNext lead note, never contact again.

---

## Coordinated cadence (email + WhatsApp)

| Day | Channel | Framework |
|---|---|---|
| 0 | Email | Vanilla Ice Cream (or Mouse Trap) |
| +2 | WhatsApp | Rotating template (only if `mobile_no` and no reply) |
| +3–4 | Email FU1 | Neutral Insight |
| +6–7 | Email Breakup | Breakup (only if 0 replies and policy allows) |

Send window: **11:00 ≤ now ≤ 19:30 local** for any send. Daily email cap 300, WhatsApp cap 10.

---

## A/B Tests

### Active
- None yet — initialise after the first 100 sends.

### Completed
| Date | Test | Winner | Learning |
|---|---|---|---|

---

## Framework Performance (auto-updated by Observer)

| Framework | Sends | Opens | Replies | Open Rate | Reply Rate |
|---|---|---|---|---|---|
| Vanilla Ice Cream | 0 | 0 | 0 | 0% | 0% |
| Mouse Trap | 0 | 0 | 0 | 0% | 0% |
| Neutral Insight | 0 | 0 | 0 | 0% | 0% |

---

## Learnings Log
- **2026-05-29:** Playbook initialised for Best Roadways. Email frameworks ported from the Bolti program (VIC = proven default). WhatsApp cadence ported from kstars-sdr (10/day cap, 48h follow-up, warm-up ramp). Stack: ERPNext + leads.csv (source) → Gemini (drafting) → Brevo (email) + WhatsApp bridge (follow-up). No Apollo.
