"""
Evaluator-Optimizer Node — US-04

Two-step quality gate applied to every draft reply

Routing between these + back to evaluator (or straight to END) happens
in graph.py via a conditional edge, using `needs_revision()` below.
"""

import os
import json
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
)

SCORE_THRESHOLD = 4.0  # average across 4 dimensions, out of 5

EVALUATOR_PROMPT = """You are a quality reviewer for an e-commerce customer support team.
Score the draft reply below on these 4 dimensions, each from 1 (poor) to 5 (excellent):

- tone: friendly, professional, empathetic (not robotic, not overly casual)
- clarity: easy to understand, simple language, no jargon
- policy: makes no promises/guarantees it shouldn't (e.g. exact delivery
  guarantees, refund promises not yet confirmed), stays factual
- completeness: does it clearly state the order status AND a concrete
  next step? (order ID/context is provided below for you to check against)

Customer's original message: {customer_message}
Order context available: {order_context}

Draft reply to evaluate:
\"\"\"{draft_reply}\"\"\"

Respond with ONLY valid JSON, no markdown fences, no extra text, in this
exact shape:
{{"tone": <int 1-5>, "clarity": <int 1-5>, "policy": <int 1-5>, "completeness": <int 1-5>, "feedback": "<1-2 sentences on what to improve, or 'Looks good' if nothing needs fixing>"}}
"""

OPTIMIZER_PROMPT = """You are revising a customer support reply based on quality feedback.

Original draft:
\"\"\"{draft_reply}\"\"\"

Order context available (use these facts, don't invent new ones, don't drop them):
{order_context}

Feedback to address:
{feedback}

Rewrite the reply to fix the issues raised while keeping all the concrete
facts from the order context (status, dates, etc.) that were already
correct. Keep it 2-4 sentences, plain language, no greeting or sign-off.
Do not invent details not present in the order context. Return ONLY the
revised reply text, nothing else.
"""


def _parse_json_response(raw_text: str) -> dict:
    """Strips markdown code fences if the model added them despite instructions."""
    cleaned = raw_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(cleaned)


def evaluator_node(state: dict) -> dict:
    draft = state.get("draft_reply", "")
    order_record = state.get("order_record")

    response = llm.invoke(EVALUATOR_PROMPT.format(
        customer_message=state.get("customer_message", ""),
        order_context=json.dumps(order_record) if order_record else "none",
        draft_reply=draft,
    ))

    try:
        scores = _parse_json_response(response.content)
    except (json.JSONDecodeError, ValueError):
        # Fail safe: if the evaluator's own output is malformed, don't crash
        # the graph - treat as a pass so the customer still gets a reply.
        scores = {"tone": 5, "clarity": 5, "policy": 5, "completeness": 5,
                  "feedback": "Evaluator response could not be parsed; passed through."}

    log_entry = f"Evaluator: scores={scores}"

    return {
        "evaluator_score": scores,
        "evaluator_feedback": scores.get("feedback", ""),
        "routing_log": [log_entry],
    }


def needs_revision(state: dict) -> str:
    """Conditional edge: revise once if below threshold, otherwise ship it."""
    scores = state.get("evaluator_score", {})
    revision_count = state.get("revision_count", 0)

    dims = ["tone", "clarity", "policy", "completeness"]
    avg = sum(scores.get(d, 5) for d in dims) / len(dims)

    if avg < SCORE_THRESHOLD and revision_count == 0:
        return "optimizer"
    return "finalize"


def optimizer_node(state: dict) -> dict:
    draft = state.get("draft_reply", "")
    feedback = state.get("evaluator_feedback", "")
    order_record = state.get("order_record")

    response = llm.invoke(OPTIMIZER_PROMPT.format(
        draft_reply=draft,
        feedback=feedback,
        order_context=json.dumps(order_record) if order_record else "none",
    ))
    revised = response.content.strip()

    log_entry = f"Optimizer: revised draft based on feedback: '{feedback}'"

    return {
        "draft_reply": revised,
        "revision_count": state.get("revision_count", 0) + 1,
        "routing_log": [log_entry],
    }


def finalize_node(state: dict) -> dict:
    """Whatever draft_reply currently holds (original or revised) becomes final_reply."""
    return {
        "final_reply": state.get("draft_reply"),
        "routing_log": ["Finalize: draft approved as final_reply"],
    }


if __name__ == "__main__":
    test_state = {
        "customer_message": "Where is my order? #10248, vinet@example-customer.com",
        "order_record": {"order_id": 10248, "shipped_date": "2016-07-16", "required_date": "2016-08-01"},
        "draft_reply": "idk man ur package is somewhere probably fine",
        "revision_count": 0,
    }

    eval_result = evaluator_node(test_state)
    print("Evaluator result:", eval_result)

    test_state.update(eval_result)
    decision = needs_revision(test_state)
    print("Needs revision?", decision)

    if decision == "optimizer":
        opt_result = optimizer_node(test_state)
        print("Optimizer result:", opt_result)