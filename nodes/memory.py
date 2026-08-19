"""
Memory Node — US-05

Runs at the end of every turn, right before the graph ends. Updates two
memory layers:

  1. window_memory (short-term) — a bounded list of the last N turns
     (customer_message + final_reply). No LLM call — just append + trim.
     This directly satisfies the "bound memory" non-functional requirement.

  2. case_summary (long-term) — a running one-paragraph summary of the
     whole case, updated via a small LLM call each turn. This is what
     lets the Copilot "remember the case" beyond the window, and is what
     US-06's handoff note will be built from later.

Persistence across turns is handled by LangGraph's checkpointer (wired in
graph.py) — this node doesn't need to worry about saving/loading itself,
it just reads/writes state normally like any other node.
"""

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
)

WINDOW_SIZE = 5  # last N turns kept in short-term memory

SUMMARY_PROMPT = """You maintain a running case summary for a customer support case.

Previous summary: {previous_summary}

New turn:
Customer: {customer_message}
Agent reply: {final_reply}

Update the summary to reflect this new turn. Keep it to 2-4 sentences,
covering: who the customer is (order ID if known), what the issue is,
what's been done so far, and current status. If the previous summary is
"none", write a fresh one from just this turn. Return ONLY the updated
summary text, nothing else.
"""


def memory_node(state: dict) -> dict:
    customer_message = state.get("customer_message", "")
    final_reply = state.get("final_reply", "")
    window = state.get("window_memory", []) or []
    previous_summary = state.get("case_summary")

    # --- Window memory: append + trim, no LLM call ---
    new_turn = {"customer_message": customer_message, "final_reply": final_reply}
    updated_window = (window + [new_turn])[-WINDOW_SIZE:]

    # --- Case summary: one LLM call to fold this turn in ---
    response = llm.invoke(SUMMARY_PROMPT.format(
        previous_summary=previous_summary or "none",
        customer_message=customer_message,
        final_reply=final_reply,
    ))
    updated_summary = response.content.strip()

    return {
        "window_memory": updated_window,
        "case_summary": updated_summary,
        "routing_log": [f"Memory: window={len(updated_window)} turns, summary updated"],
    }


if __name__ == "__main__":
    state1 = {
        "customer_message": "Where is my order #10248?",
        "final_reply": "Your order shipped July 16th and is in transit, arriving Aug 1st.",
        "window_memory": [],
        "case_summary": None,
    }
    result1 = memory_node(state1)
    print("After turn 1:")
    print("  Window:", result1["window_memory"])
    print("  Summary:", result1["case_summary"])

    state2 = {
        "customer_message": "Actually I want to return it instead, it's damaged",
        "final_reply": "I'm sorry it arrived damaged. Since it's within our return window, I'll send a prepaid label.",
        "window_memory": result1["window_memory"],
        "case_summary": result1["case_summary"],
    }
    result2 = memory_node(state2)
    print("\nAfter turn 2:")
    print("  Window:", result2["window_memory"])
    print("  Summary:", result2["case_summary"])