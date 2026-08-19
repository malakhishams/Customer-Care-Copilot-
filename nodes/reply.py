"""
Reply Node — US-01

Three cases, handled differently on purpose:
  - missing_fields non-empty  -> template ask (deterministic, no LLM needed
    to say "please provide X")
  - order_found == False      -> template fallback (deterministic apology +
    next step)
  - order_found == True       -> LLM-drafted reply (this is where "simple
    language" summarizing status/dates/next-step genuinely benefits from
    an LLM, unlike the router's regex extraction)

NOTE: this writes to `final_reply` for now, since US-04 (evaluator-optimizer)
doesn't exist yet. Once we build US-04, this node's LLM output becomes
`draft_reply` instead, and the evaluator-optimizer produces the real
`final_reply` after scoring/revising it.
"""

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
)

DRAFT_PROMPT = """You are a customer support assistant for an e-commerce company.
Write a short, friendly, plain-language reply to a customer asking about their order.

Use this order data:
- Order ID: {order_id}
- Order date: {order_date}
- Required/expected delivery date: {required_date}
- Shipped date: {shipped_date}
- Shipping to: {ship_city}, {ship_country}
- Carrier: {carrier}

{tracking_section}

Include: current status, the key dates in plain language (not raw timestamps),
and the next expected step. If live tracking evidence is provided above,
mention it as proof the customer can trust (e.g. "as of [date], your package
was scanned in transit"). Keep it to 2-4 sentences. Do not invent details
not provided above — especially do not invent tracking URLs or links that
weren't given to you. Do not include a greeting like "Dear customer" or a
sign-off — just the message body.
"""


def _template_missing_info(missing_fields: list[str]) -> str:
    asks = []
    if "customer_email" in missing_fields:
        asks.append("the email address on your order")
    if "order_id" in missing_fields:
        asks.append("your order number")
    joined = " and ".join(asks) if asks else "a bit more information"
    return f"Happy to help! Could you share {joined} so I can look up your order?"


def _template_not_found() -> str:
    return (
        "I couldn't find an order matching that information. "
        "Could you double-check your order number and the email used for the order? "
        "If it still doesn't turn up, I can connect you with a human agent."
    )


def _draft_found_reply(order_record: dict, tracking_status: dict | None) -> str:
    if tracking_status:
        tracking_section = (
            "Live tracking evidence (from the carrier, use this as proof):\n"
            f"- Status: {tracking_status.get('status')}\n"
            f"- Details: {tracking_status.get('status_details')}\n"
            f"- As of: {tracking_status.get('status_date')}\n"
            f"- ETA: {tracking_status.get('eta')}"
        )
    else:
        tracking_section = "No live tracking evidence available for this order."

    prompt = DRAFT_PROMPT.format(
        order_id=order_record.get("order_id"),
        order_date=order_record.get("order_date"),
        required_date=order_record.get("required_date"),
        shipped_date=order_record.get("shipped_date"),
        ship_city=order_record.get("ship_city"),
        ship_country=order_record.get("ship_country"),
        carrier=order_record.get("carrier"),
        tracking_section=tracking_section,
    )
    response = llm.invoke(prompt)
    return response.content.strip()


def _clarify_return_reason_template() -> str:
    return (
        "Good news — this order is eligible for a return! To help you along, "
        "could you let me know: was the item unused/unopened, opened but not used, "
        "or did it arrive damaged?"
    )


def reply_node(state: dict) -> dict:
    missing_fields = state.get("missing_fields", [])
    order_found = state.get("order_found")
    order_record = state.get("order_record")
    intent = state.get("intent")

    if missing_fields:
        reply = _template_missing_info(missing_fields)
        log_entry = "Reply: asked for missing info (template, no LLM call)"
        is_llm_draft = False
    elif order_found is False:
        reply = _template_not_found()
        log_entry = "Reply: order not found (template, no LLM call)"
        is_llm_draft = False
    elif intent == "returns" and order_found is True:
        return_plan = state.get("return_plan")
        return_eligible = state.get("return_eligible")
        if return_plan:
            reply = return_plan
            log_entry = "Reply: return plan generated (template, no LLM call)"
        elif return_eligible is False:
            # 14-day policy window is defined in returns.py — hardcoded here
            # too since reply_node stays decoupled from returns_node's
            # internal date math (deliberate, not an oversight).
            reply = (
                "I'm sorry, but this order is outside our 14-day return "
                "window. If there's a special circumstance, I can connect you with a human "
                "agent to review your case."
            )
            log_entry = "Reply: return not eligible (template, no LLM call)"
        else:
            reply = _clarify_return_reason_template()
            log_entry = "Reply: asked for return condition (template, no LLM call)"
        is_llm_draft = False
    elif order_found is True and order_record:
        tracking_status = state.get("tracking_status")
        reply = _draft_found_reply(order_record, tracking_status)
        log_entry = "Reply: order found, drafted via LLM" + (
            " (with live tracking evidence)" if tracking_status else " (no tracking evidence)"
        )
        is_llm_draft = True
    else:
        # Shouldn't normally happen, but never leave the customer with nothing.
        reply = "Sorry, something went wrong on our end. Let me get a human agent to help."
        log_entry = "Reply: fallback — unexpected state"
        is_llm_draft = False

    return {
        "draft_reply": reply,
        "is_llm_draft": is_llm_draft,
        "routing_log": [log_entry],
    }


if __name__ == "__main__":
    missing_state = {"missing_fields": ["order_id"], "order_found": None, "order_record": None}
    print("Missing info:", reply_node(missing_state)["draft_reply"], "\n")

    not_found_state = {"missing_fields": [], "order_found": False, "order_record": None}
    print("Not found:", reply_node(not_found_state)["draft_reply"], "\n")

    found_state = {
        "missing_fields": [],
        "order_found": True,
        "order_record": {
            "order_id": 10248,
            "order_date": "2016-07-04",
            "required_date": "2016-08-01",
            "shipped_date": "2016-07-16",
            "ship_city": "Reims",
            "ship_country": "France",
            "carrier": "shippo",
        },
    }
    print("Found (no tracking):", reply_node(found_state)["draft_reply"], "\n")

    found_state_with_tracking = dict(found_state)
    found_state_with_tracking["tracking_status"] = {
        "status": "TRANSIT",
        "status_details": "Your shipment has departed from the origin.",
        "status_date": "2026-08-17T20:41:57Z",
        "eta": "2026-08-19T23:34:13Z",
    }
    print("Found (with tracking):", reply_node(found_state_with_tracking)["draft_reply"])