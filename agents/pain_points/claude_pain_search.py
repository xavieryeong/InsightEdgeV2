"""
Agentic web-search loop for PainPointAgent.

Uses Claude's server-side web_search_20250305 tool.
Python drives the loop; Claude decides which searches to run and what to keep.
"""
from __future__ import annotations

from agents.base import safe_create
from agents.pain_points.config import MAX_SEARCH_ITERATIONS


def run_pain_search(
    client,
    model: str,
    system_prompt: str,
    user_message: str,
    max_tokens: int = 8192,
) -> tuple[str, list[str], int, int]:
    """
    Run the agentic web-search loop.

    Returns
    -------
    (raw_text, limitations, input_tokens, output_tokens)
    """
    messages = [{"role": "user", "content": user_message}]
    tools = [{"type": "web_search_20250305", "name": "web_search"}]
    limitations: list[str] = []
    input_tokens = 0
    output_tokens = 0

    for iteration in range(MAX_SEARCH_ITERATIONS):
        response = safe_create(
            client,
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            tools=tools,
            messages=messages,
        )
        input_tokens += response.usage.input_tokens
        output_tokens += response.usage.output_tokens

        text_output = "\n".join(
            b.text
            for b in response.content
            if hasattr(b, "type") and b.type == "text"
        )

        if response.stop_reason == "end_turn":
            return text_output, limitations, input_tokens, output_tokens

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": b.id,
                        "content": "",
                    }
                    for b in response.content
                    if hasattr(b, "type") and b.type == "tool_use"
                ],
            })
            continue

        limitations.append(
            f"Pain search stopped at iteration {iteration}: {response.stop_reason}"
        )
        if text_output:
            return text_output, limitations, input_tokens, output_tokens
        return "", limitations, input_tokens, output_tokens

    limitations.append(
        f"Pain search reached maximum iterations ({MAX_SEARCH_ITERATIONS})."
    )
    return "", limitations, input_tokens, output_tokens
