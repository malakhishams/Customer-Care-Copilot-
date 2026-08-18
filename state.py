"""
Shared graph state for the Customer Care Copilot.
"""

from typing import TypedDict, Optional, Annotated
import operator


class CustomerCareState(TypedDict):

    customer_message: str                       # latest raw message from the customer
    customer_email: Optional[str]                # collected from customer, or resolved via DB
    order_id: Optional[str]                       # collected from customer
    missing_fields: list[str]                     # what the router still needs before it can proceed

    # Order Lookup (US-01) —> result of the DB tool call
    order_record: Optional[dict]                  # row from Orders (+ joined CustomerContacts/Shipments)
    order_found: Optional[bool]

    final_reply: Optional[str]                    # customer-facing message [output]

    # Observability (Non-functional requirement: logs)
    routing_log: Annotated[list[str], operator.add]     # e.g. "Missing order_id, asking customer"
    tool_call_log: Annotated[list[dict], operator.add]  # {"tool": "db_tool", "input": ..., "output": ...}