"""
Shared graph state for the Customer Care Copilot.

Built incrementally, one User Story at a time. Right now this only holds
what US-01 (Order Lookup) needs. Fields for tracking, returns, evaluator,
memory, and handoff will be added when we build those USs.
"""

from typing import TypedDict, Optional, Annotated
import operator


class CustomerCareState(TypedDict):
    # ---------------------------------------------------------------
    # Conversation input
    # ---------------------------------------------------------------
    customer_message: str                       # latest raw message from the customer

    # ---------------------------------------------------------------
    # Identity / slot-filling (US-01)
    # ---------------------------------------------------------------
    customer_email: Optional[str]                # collected from customer, or resolved via DB
    order_id: Optional[str]                       # collected from customer
    missing_fields: list[str]                     # what the router still needs before it can proceed

    # ---------------------------------------------------------------
    # Intent (US-02/US-03) — LLM classifies once returns enters the picture
    # ---------------------------------------------------------------
    intent: Optional[str]                          # "order_status" (default) or "returns"

    # ---------------------------------------------------------------
    # Order Lookup (US-01) — result of the DB tool call
    # ---------------------------------------------------------------
    order_record: Optional[dict]                  # row from Orders (+ joined CustomerContacts/Shipments)
    order_found: Optional[bool]

    # ---------------------------------------------------------------
    # Tracking (US-02) — result of the Shippo API tool call
    # ---------------------------------------------------------------
    tracking_status: Optional[dict]                # {"status", "status_details", "status_date", "eta"}
    tracking_available: Optional[bool]              # False if order has no tracking_number, or Shippo call failed

    # ---------------------------------------------------------------
    # Returns (US-03)
    # ---------------------------------------------------------------
    return_eligible: Optional[bool]                 # within the 14-day policy window
    return_reason: Optional[str]                    # "opened" | "unused" | "damaged" — from clarifying question
    awaiting_return_reason: bool                    # True if we've asked but haven't gotten this yet (multi-turn)
    return_plan: Optional[str]                      # generated instructions once eligible + reason known

    # ---------------------------------------------------------------
    # Output
    # ---------------------------------------------------------------
    draft_reply: Optional[str]                    # produced by reply_node, before quality gate
    is_llm_draft: bool                             # True only if reply_node called the LLM (skips evaluator otherwise)

    # ---------------------------------------------------------------
    # Evaluator-Optimizer (US-04) — quality/brand-safety gate
    # ---------------------------------------------------------------
    evaluator_score: Optional[dict]                # {"tone": .., "clarity": .., "policy": .., "completeness": ..}
    evaluator_feedback: Optional[str]               # what's wrong, feeds the optimizer's revision prompt
    revision_count: int                             # 0 = not yet revised, 1 = revised once (stop after this)
    final_reply: Optional[str]                      # what actually gets "sent" — evaluator-optimizer's output

    # ---------------------------------------------------------------
    # Observability (Non-functional requirement: logs)
    # ---------------------------------------------------------------
    routing_log: Annotated[list[str], operator.add]     # e.g. "Missing order_id, asking customer"
    tool_call_log: Annotated[list[dict], operator.add]  # {"tool": "db_tool", "input": ..., "output": ...}