"""
Chat Runner — Customer Care Copilot

Interactive command-line loop. Each conversation gets a thread_id, which
LangGraph's checkpointer uses to persist state (window_memory, case_summary,
customer_email, order_id, etc.) automatically between turns — you don't
need to manually pass the previous state back in.

Run:
    python main.py
"""

import uuid
from graph import graph
from nodes.handoff import handoff_node

# Fields that must be RESET every turn (ephemeral, per-message) vs fields
# that should PERSIST across turns (identity, memory) via the checkpointer.
# Anything NOT in this reset dict keeps its value from the previous turn
# automatically.
def fresh_turn_input(customer_message: str) -> dict:
    return {
        "customer_message": customer_message,
        "missing_fields": [],
        "intent": None,
        "order_record": None,
        "order_found": None,
        "tracking_status": None,
        "tracking_available": None,
        "return_eligible": None,
        "awaiting_return_reason": False,
        "return_plan": None,
        "draft_reply": None,
        "is_llm_draft": False,
        "evaluator_score": None,
        "evaluator_feedback": None,
        "revision_count": 0,
        "final_reply": None,
        "routing_log": [],
        "tool_call_log": [],
    }


def run_chat():
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    print("Customer Care Copilot — type 'quit' to end, 'debug' to toggle logs, 'handoff' for a supervisor note\n")
    show_debug = False

    while True:
        user_input = input("You: ").strip()

        if user_input.lower() == "quit":
            print("\nSession ended.")
            break

        if user_input.lower() == "debug":
            show_debug = not show_debug
            print(f"[debug logging {'ON' if show_debug else 'OFF'}]")
            continue

        if user_input.lower() == "handoff":
            # Read current state from the checkpointer without advancing the
            # conversation — handoff is a snapshot, not a new turn.
            current_state = graph.get_state(config).values
            result = handoff_node(current_state)
            print(f"\n--- Handoff Note ---\n{result['handoff_note']}\n---------------------\n")
            continue

        if not user_input:
            continue

        turn_input = fresh_turn_input(user_input)
        result = graph.invoke(turn_input, config=config)

        print(f"\nCopilot: {result['final_reply']}\n")

        if show_debug:
            print("--- DEBUG ---")
            print("Routing log:", result["routing_log"])
            print("Tool call log:", result["tool_call_log"])
            print("Case summary:", result.get("case_summary"))
            print("Window memory size:", len(result.get("window_memory", [])))
            print("-------------\n")


if __name__ == "__main__":
    run_chat()