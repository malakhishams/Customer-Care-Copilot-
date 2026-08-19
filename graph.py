"""
Graph — US-01 (Order Lookup end-to-end)

Flow:
    START -> router -> [conditional] -> order_lookup -> reply -> END
                     -> [conditional] -> reply (skip lookup)  -> END

If the router determines fields are still missing, we skip order_lookup
entirely (no point calling the DB tool with incomplete info) and go
straight to reply_node, which asks the customer for what's missing.
"""

from langgraph.graph import StateGraph, START, END

from state import CustomerCareState
from nodes.router import router_node
from nodes.order_lookup import order_lookup_node
from nodes.tracking import tracking_node
from nodes.reply import reply_node
from nodes.evaluator_optimizer import evaluator_node, optimizer_node, finalize_node, needs_revision


def route_after_router(state: CustomerCareState) -> str:
    """Conditional edge: decide whether we have enough info to look up the order."""
    if state.get("missing_fields"):
        return "reply"          # skip lookup, ask the customer for what's missing
    return "order_lookup"       # we have both fields, proceed to the DB tool


def route_after_reply(state: CustomerCareState) -> str:
    """Conditional edge: only LLM-drafted replies need the quality gate.
    Deterministic templates (missing-info asks, not-found fallbacks) are
    already known-good and skip straight to finalize — saves API calls."""
    if state.get("is_llm_draft"):
        return "evaluator"
    return "finalize"


def build_graph():
    builder = StateGraph(CustomerCareState)

    builder.add_node("router", router_node)
    builder.add_node("order_lookup", order_lookup_node)
    builder.add_node("tracking", tracking_node)
    builder.add_node("reply", reply_node)
    builder.add_node("evaluator", evaluator_node)
    builder.add_node("optimizer", optimizer_node)
    builder.add_node("finalize", finalize_node)

    builder.add_edge(START, "router")

    builder.add_conditional_edges(
        "router",
        route_after_router,
        {
            "reply": "reply",
            "order_lookup": "order_lookup",
        },
    )

    builder.add_edge("order_lookup", "tracking")
    builder.add_edge("tracking", "reply")

    # Only LLM-drafted replies go through the evaluator-optimizer gate;
    # templates (missing-info, not-found) are already known-good and skip
    # straight to finalize.
    builder.add_conditional_edges(
        "reply",
        route_after_reply,
        {
            "evaluator": "evaluator",
            "finalize": "finalize",
        },
    )

    # After evaluating: revise once if below threshold, otherwise finalize.
    # `needs_revision` checks revision_count, so this can't loop forever -
    # after one optimizer pass, revision_count=1 forces "finalize" next time
    # through, regardless of the new score.
    builder.add_conditional_edges(
        "evaluator",
        needs_revision,
        {
            "optimizer": "optimizer",
            "finalize": "finalize",
        },
    )

    # After revising, loop back to the evaluator for an honest re-score
    # rather than trusting the optimizer blindly.
    builder.add_edge("optimizer", "evaluator")

    builder.add_edge("finalize", END)

    return builder.compile()


graph = build_graph()


if __name__ == "__main__":
    test_cases = [
        "Where is my order? #10248, vinet@example-customer.com",
        "I want to know about my package",  # missing everything
        "my order is 99999999, email is vinet@example-customer.com",  # not found
    ]

    for msg in test_cases:
        print(f"\n--- Customer: {msg} ---")
        initial_state = {
            "customer_message": msg,
            "customer_email": None,
            "order_id": None,
            "missing_fields": [],
            "order_record": None,
            "order_found": None,
            "tracking_status": None,
            "tracking_available": None,
            "draft_reply": None,
            "is_llm_draft": False,
            "evaluator_score": None,
            "evaluator_feedback": None,
            "revision_count": 0,
            "final_reply": None,
            "routing_log": [],
            "tool_call_log": [],
        }
        result = graph.invoke(initial_state)
        print("Final reply:", result["final_reply"])
        print("Evaluator score:", result["evaluator_score"])
        print("Revision count:", result["revision_count"])
        print("Routing log:", result["routing_log"])
        print("Tool call log:", result["tool_call_log"])