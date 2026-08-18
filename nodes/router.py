"""
router Node — US-01 (Order Lookup slot-filling)

Reads the customer's raw message, extracts email and/or order ID using
regex 
Writes back to state:
  - customer_email / order_id (if found in this message)
  - missing_fields (what's still needed before Order Lookup can run)
  - routing_log entry explaining the decision
"""

import re

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# Matches things like: "10248", "#10248", "order 10248", "order number 10248"
ORDER_ID_PATTERN = re.compile(r"(?:order\s*(?:number|#|no\.?)?\s*)?#?(\d{4,6})", re.IGNORECASE)


def extract_email(message: str) -> str | None:
    match = EMAIL_PATTERN.search(message)
    return match.group(0) if match else None


def extract_order_id(message: str) -> str | None:
    match = ORDER_ID_PATTERN.search(message)
    return match.group(1) if match else None


def router_node(state: dict) -> dict:
    """
    LangGraph node. Takes the current state, returns a partial state update
    (LangGraph merges this into the full state automatically).
    """
    message = state["customer_message"]

    
    found_email = extract_email(message)
    found_order_id = extract_order_id(message)

    customer_email = found_email or state.get("customer_email")
    order_id = found_order_id or state.get("order_id")

    missing = []
    if not customer_email and not order_id:
        missing.append("order_id_or_email")

    log_entry = (
        f"Router: email={'found' if customer_email else 'missing'}, "
        f"order_id={'found' if order_id else 'missing'}"
    )

    return {
        "customer_email": customer_email,
        "order_id": order_id,
        "missing_fields": missing,
        "routing_log": [log_entry],
    }


if __name__ == "__main__":
    # Quick manual tests
    test_messages = [
        "Where is my order? It's #10248",
        "my email is vinet@example-customer.com",
        "order number 10248 please",
        "I want to know about my package",  # nothing extractable
    ]
    for msg in test_messages:
        fake_state = {"customer_message": msg, "customer_email": None, "order_id": None}
        result = router_node(fake_state)
        print(f"'{msg}' -> {result}")