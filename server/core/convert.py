"""
Anthropic ↔ OpenAI format conversion utilities.
"""

import json

from core.config import logger


def convert_anthropic_to_openai(anthropic_body: dict) -> dict:
    """Convert Anthropic API request format to OpenAI format."""
    openai_body = {
        "model": anthropic_body.get("model"),
        "messages": [],
        "stream": anthropic_body.get("stream", False),
    }

    if "max_tokens" in anthropic_body:
        openai_body["max_tokens"] = anthropic_body["max_tokens"]
    if "temperature" in anthropic_body:
        openai_body["temperature"] = anthropic_body["temperature"]
    if "top_p" in anthropic_body:
        openai_body["top_p"] = anthropic_body["top_p"]
    if "stop_sequences" in anthropic_body:
        openai_body["stop"] = anthropic_body["stop_sequences"]

    if "tools" in anthropic_body:
        openai_body["tools"] = []
        for tool in anthropic_body["tools"]:
            openai_body["tools"].append({
                "type": "function",
                "function": {
                    "name": tool.get("name"),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {})
                }
            })
        logger.info(f"[Convert] Converted {len(openai_body['tools'])} tools to OpenAI format")

    if "system" in anthropic_body:
        if isinstance(anthropic_body["system"], str):
            openai_body["messages"].append({
                "role": "system",
                "content": anthropic_body["system"]
            })
        elif isinstance(anthropic_body["system"], list):
            system_content = ""
            for block in anthropic_body["system"]:
                if block.get("type") == "text":
                    system_content += block.get("text", "")
            if system_content:
                openai_body["messages"].append({
                    "role": "system",
                    "content": system_content
                })

    for msg in anthropic_body.get("messages", []):
        role = msg.get("role")
        content = msg.get("content")

        if isinstance(content, str):
            openai_body["messages"].append({
                "role": role,
                "content": content
            })
        elif isinstance(content, list):
            openai_content = []
            tool_calls = []
            has_tool_results = False

            for block in content:
                if block.get("type") == "text":
                    openai_content.append({
                        "type": "text",
                        "text": block.get("text", "")
                    })
                elif block.get("type") == "image":
                    source = block.get("source", {})
                    if source.get("type") == "base64":
                        openai_content.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{source.get('media_type', 'image/png')};base64,{source.get('data', '')}"
                            }
                        })
                elif block.get("type") == "tool_use":
                    tool_calls.append({
                        "id": block.get("id"),
                        "type": "function",
                        "function": {
                            "name": block.get("name"),
                            "arguments": json.dumps(block.get("input", {}))
                        }
                    })
                elif block.get("type") == "tool_result":
                    has_tool_results = True
                    content = block.get("content")

                    if isinstance(content, list):
                        text_parts = []
                        for content_block in content:
                            if isinstance(content_block, dict) and content_block.get("type") == "text":
                                text_parts.append(content_block.get("text", ""))
                        content = "\n".join(text_parts) if text_parts else json.dumps(content)
                    elif not isinstance(content, str):
                        content = json.dumps(content)

                    if block.get("is_error"):
                        content = f"ERROR: {content}"

                    openai_body["messages"].append({
                        "role": "tool",
                        "tool_call_id": block.get("tool_use_id"),
                        "content": content
                    })

            if not has_tool_results:
                msg_dict = {
                    "role": role,
                    "content": openai_content if len(openai_content) > 1 else (openai_content[0]["text"] if openai_content else "")
                }

                if tool_calls:
                    msg_dict["tool_calls"] = tool_calls

                openai_body["messages"].append(msg_dict)

    return openai_body


def convert_openai_to_anthropic(openai_response: dict) -> dict:
    """Convert OpenAI API response format to Anthropic format."""
    choice = openai_response.get("choices", [{}])[0]
    message = choice.get("message", {})
    finish_reason = choice.get("finish_reason")

    stop_reason_map = {
        "stop": "end_turn",
        "length": "max_tokens",
        "tool_calls": "tool_use",
        "content_filter": "end_turn",
        "function_call": "tool_use"
    }

    anthropic_response = {
        "id": openai_response.get("id", ""),
        "type": "message",
        "role": "assistant",
        "content": [],
        "model": openai_response.get("model", ""),
        "stop_reason": stop_reason_map.get(finish_reason, finish_reason or "end_turn"),
        "usage": {
            "input_tokens": openai_response.get("usage", {}).get("prompt_tokens", 0),
            "output_tokens": openai_response.get("usage", {}).get("completion_tokens", 0)
        }
    }

    content = message.get("content", "")
    if content:
        anthropic_response["content"].append({
            "type": "text",
            "text": content
        })

    tool_calls = message.get("tool_calls", [])
    if tool_calls:
        for tool_call in tool_calls:
            if tool_call.get("type") == "function":
                function = tool_call.get("function", {})
                try:
                    arguments = json.loads(function.get("arguments", "{}"))
                except json.JSONDecodeError:
                    arguments = {}

                anthropic_response["content"].append({
                    "type": "tool_use",
                    "id": tool_call.get("id"),
                    "name": function.get("name"),
                    "input": arguments
                })

    return anthropic_response


def convert_openai_stream_to_anthropic(chunk: bytes) -> bytes:
    """Convert OpenAI streaming format to Anthropic streaming format."""
    return chunk
