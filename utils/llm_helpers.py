"""
Shared LLM response helper.

response.content from langchain_google_genai can be either a plain string
OR a list of content blocks (depending on the response format Gemini
returns) — this bit us with an AttributeError when .strip() was called
directly on a list. Every node that calls llm.invoke() should extract text
through this helper instead of touching response.content directly.
"""


def extract_text(response) -> str:
    content = response.content

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        # Content blocks are typically dicts with a "text" key, or plain
        # strings — handle both, join in order, ignore anything else.
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and "text" in block:
                parts.append(block["text"])
        return "".join(parts).strip()

    # Fallback: never crash, just stringify whatever we got.
    return str(content).strip()