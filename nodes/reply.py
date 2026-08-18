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

Include: current status, the key dates in plain language (not raw timestamps),
and the next expected step. Keep it to 2-4 sentences. Do not invent details
not provided above. Do not include a greeting like "Dear customer" or a
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


def _draft_found_reply(order_record: dict) -> str:
    prompt = DRAFT_PROMPT.format(
        order_id=order_record.get("order_id"),
        order_date=order_record.get("order_date"),
        required_date=order_record.get("required_date"),
        shipped_date=order_record.get("shipped_date"),
        ship_city=order_record.get("ship_city"),
        ship_country=order_record.get("ship_country"),
        carrier=order_record.get("carrier"),
    )
    response = llm.invoke(prompt)
    return response.content.strip()


def reply_node(state: dict) -> dict:
    missing_fields = state.get("missing_fields", [])
    order_found = state.get("order_found")
    order_record = state.get("order_record")

    if missing_fields:
        reply = _template_missing_info(missing_fields)
        log_entry = "Reply: asked for missing info (template, no LLM call)"
    elif order_found is False:
        reply = _template_not_found()
        log_entry = "Reply: order not found (template, no LLM call)"
    elif order_found is True and order_record:
        reply = _draft_found_reply(order_record)
        log_entry = "Reply: order found, drafted via LLM"
    else:
        # Shouldn't normally happen, but never leave the customer with nothing.
        reply = "Sorry, something went wrong on our end. Let me get a human agent to help."
        log_entry = "Reply: fallback — unexpected state"

    return {
        "draft_reply": reply,
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
    print("Found (LLM draft):", reply_node(found_state)["draft_reply"])