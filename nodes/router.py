"""
Router Node — US-01 (slot-filling) + US-03 (intent classification)

Two separate mechanisms, deliberately different:
  1. Email/order_id extraction — regex (rule-based). Fixed, predictable
     patterns; an LLM call would add cost with zero benefit.
  2. Intent classification (order_status vs returns) — LLM-based. Return
     requests are phrased too many different ways ("I want to return this",
     "this doesn't work, can I send it back", "not happy with my order")
     for keyword-matching to reliably catch — this is a case where
     reasoning genuinely earns its cost, unlike #1.

Writes back to state:
  - customer_email / order_id (if found in this message)
  - missing_fields (what's still needed before Order Lookup can run)
  - intent ("order_status" or "returns")
  - routing_log entry explaining the decision
"""

import os
import re
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
)

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# Matches things like: "10248", "#10248", "order 10248", "order number 10248"
ORDER_ID_PATTERN = re.compile(r"(?:order\s*(?:number|#|no\.?)?\s*)?#?(\d{4,6})", re.IGNORECASE)

INTENT_PROMPT = """Classify the customer's message into exactly one category:
- "returns": the customer wants to return, refund, exchange, or send back
  an item, or is unhappy with a product and considering returning it.
- "order_status": anything else (asking where an order is, tracking,
  general questions, or messages that just contain an email/order number
  with no other context).

Customer message: "{message}"

Respond with ONLY the category word, nothing else: either "returns" or "order_status".
"""


def extract_email(message: str) -> str | None:
    match = EMAIL_PATTERN.search(message)
    return match.group(0) if match else None


def extract_order_id(message: str) -> str | None:
    match = ORDER_ID_PATTERN.search(message)
    return match.group(1) if match else None


def classify_intent(message: str) -> str:
    response = llm.invoke(INTENT_PROMPT.format(message=message))
    result = response.content.strip().lower()
    # Fail safe: if the LLM returns anything unexpected, default to the
    # safer/simpler path rather than crash or guess wrong.
    return "returns" if "return" in result else "order_status"


def router_node(state: dict) -> dict:
    """
    LangGraph node. Takes the current state, returns a partial state update
    (LangGraph merges this into the full state automatically).
    """
    message = state["customer_message"]

    # Only extract if we don't already have it from a previous turn —
    # avoids overwriting a valid order_id with None on a follow-up message
    # that doesn't repeat it.
    found_email = extract_email(message)
    found_order_id = extract_order_id(message)

    customer_email = found_email or state.get("customer_email")
    order_id = found_order_id or state.get("order_id")

    # Both email AND order_id are required as a basic identity check —
    # order_id alone would let anyone who guesses/knows a number pull up
    # another customer's shipping address (privacy requirement).
    missing = []
    if not customer_email:
        missing.append("customer_email")
    if not order_id:
        missing.append("order_id")

    intent = classify_intent(message)

    log_entry = (
        f"Router: email={'found' if customer_email else 'missing'}, "
        f"order_id={'found' if order_id else 'missing'}, intent={intent}"
    )

    return {
        "customer_email": customer_email,
        "order_id": order_id,
        "missing_fields": missing,
        "intent": intent,
        "routing_log": [log_entry],
    }


if __name__ == "__main__":
    # Quick manual tests
    test_messages = [
        "Where is my order? It's #10248",
        "my email is vinet@example-customer.com",
        "order number 10248 please",
        "I want to know about my package",  # nothing extractable, order_status
        "I want to return this, it arrived damaged",  # returns intent
        "This doesn't work, can I send it back? order 10248",  # returns intent
    ]
    for msg in test_messages:
        fake_state = {"customer_message": msg, "customer_email": None, "order_id": None}
        result = router_node(fake_state)
        print(f"'{msg}' -> intent={result['intent']}, email={result['customer_email']}, order_id={result['order_id']}")