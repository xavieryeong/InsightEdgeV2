"""
Agentic web-search loop for RegulatoryImpactAgent.

Uses Claude's server-side web_search_20250305 tool so every URL in the
output is a real, verifiable page — not a hallucinated citation.
"""
from __future__ import annotations

from agents.base import safe_create

_MAX_SEARCH_ITERATIONS = 8


def run_reg_search(
    client,
    model: str,
    system_prompt: str,
    user_message: str,
    max_tokens: int = 8192,
) -> tuple[str, list[str], int, int]:
    """
    Run the agentic regulatory web-search loop.

    Returns
    -------
    (raw_text, limitations, input_tokens, output_tokens)
    """
    messages = [{"role": "user", "content": user_message}]
    tools = [{"type": "web_search_20250305", "name": "web_search"}]
    limitations: list[str] = []
    input_tokens = 0
    output_tokens = 0

    for iteration in range(_MAX_SEARCH_ITERATIONS):
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
            f"Regulatory search stopped at iteration {iteration}: "
            f"{response.stop_reason}"
        )
        if text_output:
            return text_output, limitations, input_tokens, output_tokens
        return "", limitations, input_tokens, output_tokens

    limitations.append(
        f"Regulatory search reached maximum iterations ({_MAX_SEARCH_ITERATIONS})."
    )
    return "", limitations, input_tokens, output_tokens
