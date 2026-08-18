"""
Tracking Node — US-02

Runs automatically after a successful order_lookup (per the brief: routing
into Tracking is triggered by "the order record contains a tracking number",
not by customer phrasing — so this is a data check, not intent classification).

If order_record has a tracking_number, calls the Shippo tool and writes the
result to state. If there's no tracking number, or the Shippo call fails,
sets tracking_available=False and moves on — reply_node will phrase the
message accordingly (this is the "safe fallback when tracking unavailable"
robustness case from the brief).
"""

from tools.shipping_tool import get_tracking_status


def tracking_node(state: dict) -> dict:
    order_record = state.get("order_record")

    if not order_record or not order_record.get("tracking_number"):
        return {
            "tracking_available": False,
            "tracking_status": None,
            "routing_log": ["Tracking: skipped — no tracking number on this order"],
        }

    carrier = order_record.get("carrier", "shippo")
    tracking_number = order_record["tracking_number"]

    result = get_tracking_status(carrier, tracking_number)

    log_entry = {
        "tool": "shipping_tool.get_tracking_status",
        "input": {"carrier": carrier, "tracking_number": tracking_number},
        "available": result["available"],
    }

    if not result["available"]:
        return {
            "tracking_available": False,
            "tracking_status": None,
            "tool_call_log": [log_entry],
            "routing_log": [f"Tracking: Shippo call failed — {result.get('error')}"],
        }

    return {
        "tracking_available": True,
        "tracking_status": result,
        "tool_call_log": [log_entry],
        "routing_log": ["Tracking: fetched live status from Shippo"],
    }


if __name__ == "__main__":
    with_tracking = {"order_record": {"carrier": "shippo", "tracking_number": "SHIPPO_DELIVERED"}}
    print("With tracking:", tracking_node(with_tracking))

    no_tracking_number = {"order_record": {"carrier": "shippo", "tracking_number": None}}
    print("No tracking number:", tracking_node(no_tracking_number))

    no_order = {"order_record": None}
    print("No order record:", tracking_node(no_order))