# Customer Care Copilot

A LangGraph-powered customer support agent for an e-commerce company. It looks up orders, fetches live shipping tracking, evaluates returns eligibility, remembers case context across turns, and runs every AI-drafted reply through an evaluator-optimizer quality gate before it's sent.

Built for the **Sprints Advanced Agentic AI course (Task 2)**.

---

## What it does

- **Order status** — collects order ID + email, looks up the order in a SQLite database, and drafts a plain-language status update.
- **Live tracking** — automatically enriches order-status replies with real tracking evidence from the Shippo API (test mode) whenever the order has a tracking number.
- **Returns** — classifies return intent, checks 14-day eligibility, asks a clarifying question (opened / unused / damaged), and generates a return plan.
- **Quality gate** — every AI-drafted reply is scored on tone, clarity, policy, and completeness, and revised once if it falls below threshold.
- **Memory** — short-term window memory (last 5 turns) and a long-term running case summary persist across the conversation via LangGraph's checkpointer, so the customer never has to repeat their email/order ID.
- **Handoff notes** — on demand, generates a one-paragraph summary for a human agent taking over the case.

---

## Architecture

```
START
  |
  v
router --(missing info)--------------> reply --> finalize --> memory --> END
  | (have email + order_id)
  v
order_lookup
  |
  +--(intent = returns)--> returns --------------+
  |                                               |
  +--(intent = order_status)--> tracking ---------+
                                                   v
                                                 reply
                                                   |
                                    (LLM-drafted?) | (template?)
                                        +----------+----------+
                                        v                     v
                                    evaluator              finalize
                                        |  ^                  |
                                (below     |                  |
                                threshold) | (re-score)        |
                                        v  |                   |
                                    optimizer                  |
                                        +--+                   |
                                                                v
                                                              memory
                                                                |
                                                                v
                                                               END
```

**Key design decisions:**

- **Tracking is data-driven, not intent-driven.** Per the brief, tracking is triggered by "the order record contains a tracking number" — not by customer phrasing. So it runs automatically after every successful order lookup for `order_status` intent, rather than needing the customer to specifically ask "where's the tracking."
- **Returns intent uses an LLM classifier; email/order-ID extraction uses regex.** Return requests are phrased too many different ways ("send it back", "this doesn't work", "not happy with it") for keyword-matching to reliably catch. Email/order ID have fixed, predictable shapes, so regex is faster and free.
- **Both email AND order ID are required** to look up an order — a basic identity check. Order ID alone would let anyone who guesses/knows a number pull up someone else's shipping address.
- **Templates skip the evaluator-optimizer.** Deterministic replies (missing-info asks, not-found fallbacks, return plans) are already known-good and don't need LLM quality-scoring — only LLM-drafted replies (order-status summaries) go through the gate. This roughly halves LLM API usage per conversation.
- **The evaluator re-scores after a revision** rather than trusting the optimizer blindly, giving an honest final score in the logs. It only revises once (per the brief) — if still below threshold after that, it ships anyway rather than looping forever.

---

## Tech stack

- **Language:** Python
- **Framework:** LangGraph
- **LLM:** Google Gemini (`gemini-3.6-flash`)
- **Database:** Northwind (SQLite), extended with two companion tables
- **Shipping API:** Shippo (test mode)
- **Memory:** LangGraph's `InMemorySaver` checkpointer + custom window/summary memory

---

## Project structure

```
Customer-Care-Copilot/
├── data/
│   └── northwind.db              # Northwind SQLite DB (download separately, see setup)
├── nodes/
│   ├── router.py                 # slot-filling (regex) + intent classification (LLM)
│   ├── order_lookup.py           # calls db_tool, identity-checked
│   ├── tracking.py                # calls shipping_tool automatically after lookup
│   ├── returns.py                 # eligibility, reason detection, return plan
│   ├── reply.py                   # drafts customer-facing replies
│   ├── evaluator_optimizer.py     # quality gate: score -> revise once -> re-score
│   ├── memory.py                  # window + summary memory, runs every turn
│   └── handoff.py                 # on-demand supervisor handoff note
├── tools/
│   ├── db_tool.py                 # Northwind order lookup (by order_id and/or email)
│   └── shipping_tool.py           # Shippo tracking API wrapper
├── utils/
│   └── llm_helpers.py             # safe text extraction from LLM responses
├── scripts/
│   ├── sanity_check.py            # verifies DB + Shippo connections work
│   └── seed_extensions.py         # adds CustomerContacts + Shipments tables to Northwind
├── demo/                          # output demos screenshots
├── state.py                       # shared LangGraph state (TypedDict)
├── graph.py                       # builds and wires the full graph
├── main.py 
├── .gitignore          
├── .env.example
└── README.md
```

---

## Setup (Windows / macOS)

### 1. Create a virtual environment

```bash
python -m venv venv
```
Windows: `venv\Scripts\activate`
macOS: `source venv/bin/activate`

### 2. Install dependencies

```bash
pip install langgraph langchain langchain-google-genai python-dotenv requests
```

### 3. Download the Northwind SQLite database

Get `northwind.db` from the [jpwhite3/northwind-SQLite3](https://github.com/jpwhite3/northwind-SQLite3) repo and place it at `data/northwind.db`.

### 4. Extend the database

Northwind is a B2B demo dataset — it has no customer emails and no shipment/tracking data, both of which this project needs. Run the seed script **once**, after downloading the DB and before running the app:

```bash
python scripts/seed_extensions.py
```

This adds two new tables (`CustomerContacts`, `Shipments`) without touching the original Northwind tables. It's idempotent — safe to re-run.

### 5. Get a Shippo test API key

Sign up at [goshippo.com](https://goshippo.com), go to Settings → API, and copy your **test-mode** key (starts with `shippo_test_...`).

### 6. Set up your `.env` file

```
GEMINI_API_KEY=your_gemini_key_here
SHIPPO_API_KEY=shippo_test_your_key_here
```

### 7. Sanity check (optional but recommended)

```bash
python scripts/sanity_check.py
```
Confirms both the DB and Shippo API are reachable before running the full app.

### 8. Run it

```bash
python main.py
```

---

## Demo script

Try this sequence for a full end-to-end demo covering every user story:

```
1. "Where is my order? #10248, vinet@example-customer.com"
   -> Order lookup + live tracking evidence + evaluator-optimizer pass (US-01, US-02, US-04)

2. "actually I want to return it, it arrived damaged"
   -> Returns flow, using the SAME order/email from turn 1 without repeating them (US-03, US-05)

3. "handoff"
   -> One-paragraph supervisor note built from the case summary (US-06)

4. "debug" (toggle any time)
   -> Shows routing_log, tool_call_log, case_summary, and window_memory size
```

---

## User stories → implementation

| User Story | Implemented in |
|---|---|
| US-01 (Order status) | `nodes/router.py`, `nodes/order_lookup.py`, `tools/db_tool.py`, `nodes/reply.py` |
| US-02 (Tracking evidence) | `nodes/tracking.py`, `tools/shipping_tool.py` |
| US-03 (Returns) | `nodes/returns.py`, intent classification in `nodes/router.py` |
| US-04 (Evaluator-Optimizer) | `nodes/evaluator_optimizer.py` |
| US-05 (Memory) | `nodes/memory.py`, checkpointer in `graph.py` |
| US-06 (Handoff summary) | `nodes/handoff.py`, `handoff` command in `main.py` |

---

## Honest notes — real issues found while building this

Documenting these because they were genuine bugs caught through testing, not things either of us anticipated upfront.

- **Identity-check leak (fixed):** the DB tool originally fell back to "most recent order for this email" whenever a *wrong* order ID was given alongside a *correct* email — silently leaking a real order instead of returning "not found." Fixed so both fields must match the same order.
- **Northwind date inconsistency:** the dataset mixes legacy rows (`YYYY-MM-DD`) with newer synthetic rows (`YYYY-MM-DD HH:MM:SS`), and has far more orders (~16,000+) than the classic Northwind dataset — likely an expanded fork. Handled with a dual-format date parser.
- **2016 vs. "now" date mismatch:** because Northwind's order dates are historical (2016) but Shippo's test-mode tracking generates "live" timestamps relative to the actual current date, the evaluator sometimes flags genuine internal inconsistencies (e.g. "your dates don't match") — which is *correct* behavior, but the optimizer's fix isn't always right either. In one run, the optimizer resolved a date conflict by standardizing on the wrong year. This is a known limitation of the optimizer's revision quality, not something we fixed given time constraints.
- **`response.content` can be a string OR a list.** Depending on the Gemini response format, `response.content` from `langchain_google_genai` sometimes returns a list of content blocks instead of a plain string, causing `AttributeError: 'list' object has no attribute 'strip'`. Fixed with a shared `extract_text()` helper (`utils/llm_helpers.py`) used everywhere an LLM response is parsed.
- **Checkpoint memory is in-process only.** We use LangGraph's `InMemorySaver`, which persists state across turns within a running session but does **not** survive an app restart. A production version would swap this for `SqliteSaver` or similar for true resume-after-restart.
- **Router re-classifies intent every turn**, even turns where intent is already known from earlier in the conversation — a minor inefficiency (one avoidable LLM call per turn) that we didn't get to optimize given time constraints.
- **Privacy masking is only applied in one place** (`order_lookup.py` masks the email in `tool_call_log`). The brief's privacy requirement ("mask sensitive fields in logs") isn't yet applied systematically across every log point — a known gap, not an oversight.

---

## Known limitations / not implemented

- Vector Recall memory (optional per the brief) — not implemented.
- Return shipment request generation via the Shipping API (optional per US-03) — not implemented; the return plan is text-only.
- Systematic privacy masking across all logs (see honest notes above).
- Automated tests — all testing was manual, via `__main__` blocks in each module and live runs of `main.py`.