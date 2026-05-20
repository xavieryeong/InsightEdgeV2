from __future__ import annotations

import re
import json

from agents.discovery.config import MAX_DISCOVERY_ITERATIONS


def run_discovery_search(
    client,
    model: str,
    system_prompt: str,
    user_message: str,
    max_tokens: int = 4096,
) -> tuple[str, list[str]]:
    """
    Agentic loop for company discovery using web_search_20250305.
    Returns (raw_text, limitations).
    """
    messages = [{"role": "user", "content": user_message}]
    tools = [{"type": "web_search_20250305", "name": "web_search"}]
    limitations: list[str] = []

    for iteration in range(MAX_DISCOVERY_ITERATIONS):
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            tools=tools,
            messages=messages,
        )

        text_output = "\n".join(
            b.text for b in response.content
            if hasattr(b, "type") and b.type == "text"
        )

        if response.stop_reason == "end_turn":
            return text_output, limitations

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            messages.append({
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": b.id, "content": ""}
                    for b in response.content
                    if hasattr(b, "type") and b.type == "tool_use"
                ],
            })
            continue

        limitations.append(
            f"Discovery search stopped at iteration {iteration}: {response.stop_reason}"
        )
        if text_output:
            return text_output, limitations
        return "", limitations

    limitations.append("Discovery search reached maximum iterations.")
    return "", limitations
