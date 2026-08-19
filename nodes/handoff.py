"""
Handoff Node — US-06

Generates a concise "handoff note" for a supervisor/agent taking over the
case — built primarily from case_summary (US-05's long-term memory), which
already tracks customer + issue + actions taken + status across turns.

This is NOT wired into the main graph's per-turn flow (a handoff note per
message would be wasteful and pointless mid-conversation). Instead, it's
called on-demand — e.g. when the customer ends the session, or an agent
requests a handoff. See main.py's 'handoff' command.
"""

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

from utils.llm_helpers import extract_text

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
)

HANDOFF_PROMPT = """Turn this case summary into a concise handoff note for a
human agent taking over this support case. One paragraph, professional tone.
Include: customer identifier, the issue, evidence/actions taken so far, and
the clear next step needed.

Case summary: {case_summary}

Order context: {order_context}

Return ONLY the handoff note text, nothing else.
"""


def handoff_node(state: dict) -> dict:
    case_summary = state.get("case_summary")
    order_record = state.get("order_record")

    if not case_summary:
        return {"handoff_note": "No case history available yet — this is a fresh session with no prior turns."}

    response = llm.invoke(HANDOFF_PROMPT.format(
        case_summary=case_summary,
        order_context=f"Order #{order_record.get('order_id')}" if order_record else "none on record",
    ))
    note = extract_text(response)

    return {
        "handoff_note": note,
        "routing_log": ["Handoff: generated supervisor note from case_summary"],
    }


if __name__ == "__main__":
    test_state = {
        "case_summary": (
            "Customer vinet@example-customer.com (order #10248) initially inquired about "
            "their order status, which was confirmed to be in transit. The customer now "
            "states the order arrived damaged and wishes to return it. The agent informed "
            "them the return is outside the 14-day window, but offered to connect them with "
            "a human agent for review under special circumstances."
        ),
        "order_record": {"order_id": 10248},
    }
    result = handoff_node(test_state)
    print("Handoff note:\n", result["handoff_note"])