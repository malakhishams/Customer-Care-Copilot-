"""
Returns Node — US-03

Multi-turn flow:
  1. First pass: order found -> check eligibility (14 days from order_date)
     -> if eligible, ask "opened/unused/damaged?" and stop (awaiting_return_reason=True)
     -> if not eligible, explain why, no clarifying question needed
  2. Second pass: return_reason already in state (detected via keyword
     matching on the customer's follow-up message) -> generate the return
     plan directly

Eligibility policy: 14 days from order_date. This is a policy we invented
for the MVP (the brief doesn't specify a window) — documented here and in
the README as a deliberate assumption.

Reason detection is keyword-based, not LLM-based: only 3 fixed categories
(opened/unused/damaged), so there's little accuracy benefit from an LLM
call, and every call saved matters given free-tier quota constraints.
"""

from datetime import datetime, timedelta

RETURN_WINDOW_DAYS = 14

REASON_KEYWORDS = {
    "damaged": ["damaged", "broken", "defective", "arrived damaged", "not working"],
    "opened": ["opened", "used it", "tried it", "opened it"],
    "unused": ["unused", "unopened", "still sealed", "never opened", "brand new"],
}


def _parse_order_date(order_date_str: str) -> datetime:
    """Handles both date formats seen in the Northwind data (see honest
    notes: legacy rows are 'YYYY-MM-DD', newer synthetic rows include time)."""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(order_date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: {order_date_str}")


def _check_eligibility(order_date_str: str) -> tuple[bool, int]:
    """Returns (eligible, days_since_order)."""
    order_date = _parse_order_date(order_date_str)
    days_since = (datetime.now() - order_date).days
    return days_since <= RETURN_WINDOW_DAYS, days_since


def _detect_reason(message: str) -> str | None:
    message_lower = message.lower()
    for reason, keywords in REASON_KEYWORDS.items():
        if any(kw in message_lower for kw in keywords):
            return reason
    return None


def _build_return_plan(order_record: dict, reason: str) -> str:
    order_id = order_record.get("order_id")
    if reason == "damaged":
        return (
            f"I'm sorry your order #{order_id} arrived damaged. Here's what happens next: "
            "we'll email you a prepaid return label within 24 hours — no need to repackage "
            "carefully, just include what you can. Once we receive it (usually 5-7 business "
            "days), your refund will be processed within 3-5 business days. Since this was "
            "damaged in transit, you won't be charged any return shipping fees."
        )
    elif reason == "unused":
        return (
            f"Since order #{order_id} is unused and unopened, you're all set for a standard "
            "return. Print the prepaid return label we'll email you, pack the item in its "
            "original packaging if possible, and drop it off at any carrier location. Once "
            "received (usually 5-7 business days), your refund will be issued within 3-5 "
            "business days."
        )
    else:  # opened
        return (
            f"Order #{order_id} is eligible for return even though it's been opened. Please "
            "repackage it as securely as you can with all original accessories included. "
            "We'll email you a prepaid return label — return shipping fees will be deducted "
            "from your refund. Once received (5-7 business days), your refund will be issued "
            "within 3-5 business days."
        )


def returns_node(state: dict) -> dict:
    order_record = state.get("order_record")
    order_found = state.get("order_found")
    existing_reason = state.get("return_reason")

    if not order_found or not order_record:
        return {
            "return_eligible": None,
            "routing_log": ["Returns: skipped — no order on record"],
        }

    # Second pass: we already have the reason, generate the plan directly.
    if existing_reason:
        plan = _build_return_plan(order_record, existing_reason)
        return {
            "return_plan": plan,
            "awaiting_return_reason": False,
            "routing_log": [f"Returns: reason already known ({existing_reason}), generated plan"],
        }

    # Try to detect the reason from THIS message, in case the customer
    # volunteered it upfront ("I want to return this, it's damaged").
    detected_reason = _detect_reason(state.get("customer_message", ""))

    eligible, days_since = _check_eligibility(order_record.get("order_date"))

    if not eligible:
        return {
            "return_eligible": False,
            "routing_log": [f"Returns: not eligible — {days_since} days since order (limit {RETURN_WINDOW_DAYS})"],
        }

    if detected_reason:
        plan = _build_return_plan(order_record, detected_reason)
        return {
            "return_eligible": True,
            "return_reason": detected_reason,
            "return_plan": plan,
            "awaiting_return_reason": False,
            "routing_log": [f"Returns: eligible, reason detected upfront ({detected_reason}), generated plan"],
        }

    # Eligible, but we don't know the reason yet — ask, and wait for next turn.
    return {
        "return_eligible": True,
        "awaiting_return_reason": True,
        "routing_log": [f"Returns: eligible ({days_since} days since order), asking for condition"],
    }


if __name__ == "__main__":
    recent_order = {"order_id": 24835, "order_date": "2023-10-15 08:23:33"}  # will be >14 days old (test data)
    old_order = {"order_id": 10248, "order_date": "2016-07-04"}

    # Case 1: eligible check on old data (won't be eligible - illustrates the check works)
    state1 = {"order_found": True, "order_record": old_order, "customer_message": "I want to return this"}
    print("Old order (not eligible):", returns_node(state1))

    # Case 2: reason volunteered upfront
    state2 = {"order_found": True, "order_record": old_order, "customer_message": "it arrived damaged, want to return"}
    print("\nDamaged, upfront:", returns_node(state2))

    # Case 3: reason already known from a previous turn (simulated)
    state3 = {"order_found": True, "order_record": old_order, "return_reason": "unused"}
    print("\nSecond turn, reason known:", returns_node(state3))