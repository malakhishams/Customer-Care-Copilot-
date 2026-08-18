from langgraph.graph import StateGraph, START, END

from state import CustomerCareState
from nodes.router import router_node
from nodes.order_lookup import order_lookup_node
from nodes.reply import reply_node


def route_after_router(state: CustomerCareState) -> str:
    """Conditional edge: decide whether we have enough info to look up the order."""
    if state.get("missing_fields"):
        return "reply"          # skip lookup, ask the customer for what's missing
    return "order_lookup"       # we have both fields, proceed to the DB tool


def build_graph():
    builder = StateGraph(CustomerCareState)

    builder.add_node("router", router_node)
    builder.add_node("order_lookup", order_lookup_node)
    builder.add_node("reply", reply_node)

    builder.add_edge(START, "router")

    builder.add_conditional_edges(
        "router",
        route_after_router,
        {
            "reply": "reply",
            "order_lookup": "order_lookup",
        },
    )

    builder.add_edge("order_lookup", "reply")
    builder.add_edge("reply", END)

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
            "final_reply": None,
            "routing_log": [],
            "tool_call_log": [],
        }
        result = graph.invoke(initial_state)
        print("Reply:", result["final_reply"])
        print("Routing log:", result["routing_log"])
        print("Tool call log:", result["tool_call_log"])