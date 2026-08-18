"""
Order Lookup Node — US-01

Calls tools/db_tool.py using customer_email and order_id already collected
by the router. 
Writes back to state:
  - order_record / order_found
  - tool_call_log entry (observability requirement: DB calls must be logged)
"""

from tools.db_tool import lookup_order


def order_lookup_node(state: dict) -> dict:
    order_id = state.get("order_id")
    customer_email = state.get("customer_email")

    if not order_id or not customer_email:
        return {
            "order_found": False,
            "order_record": None,
            "routing_log": ["Order Lookup: skipped — missing order_id or customer_email"],
        }

    result = lookup_order(order_id=order_id, email=customer_email)

    # Privacy: log that the tool was called and what it returned, but mask
    # the email in the log itself (non-functional requirement).
    masked_email = _mask_email(customer_email)
    log_entry = {
        "tool": "db_tool.lookup_order",
        "input": {"order_id": order_id, "email": masked_email},
        "found": result["found"],
    }

    return {
        "order_found": result["found"],
        "order_record": result["order"],
        "tool_call_log": [log_entry],
    }


def _mask_email(email: str) -> str:
    """vinet@example-customer.com -> vi***@example-customer.com"""
    if not email or "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    visible = local[:2] if len(local) > 2 else local[:1]
    return f"{visible}***@{domain}"


if __name__ == "__main__":
    # Quick manual tests
    found_state = {"order_id": "10248", "customer_email": "vinet@example-customer.com"}
    print("Found case:", order_lookup_node(found_state))

    not_found_state = {"order_id": "99999999", "customer_email": "vinet@example-customer.com"}
    print("Not found case:", order_lookup_node(not_found_state))

    missing_state = {"order_id": None, "customer_email": None}
    print("Missing info case:", order_lookup_node(missing_state))