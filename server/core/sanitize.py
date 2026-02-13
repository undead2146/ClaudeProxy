"""
Payload sanitization & transformation helpers.

Handles thinking blocks, beta header filtering, custom provider sanitization,
and tool input fixing for streaming responses.
"""

import json
import hashlib

from core.config import logger


def generate_signature(thinking_content: str) -> str:
    """Generate a valid signature for thinking block."""
    return hashlib.sha256(thinking_content.encode()).hexdigest()[:32]


def fix_thinking_blocks(body_json: dict, has_thinking_beta: bool, use_real_anthropic: bool = False) -> dict:
    """
    Strip thinking blocks from messages when sending to Anthropic.
    Anthropic's API doesn't accept thinking blocks with signatures.
    """
    if not use_real_anthropic:
        return body_json

    if 'messages' in body_json:
        for message in body_json['messages']:
            if isinstance(message.get('content'), list):
                message['content'] = [
                    block for block in message['content']
                    if block.get('type') != 'thinking'
                ]

    return body_json


def has_thinking_in_beta(beta_header: str) -> bool:
    """Check if thinking is enabled in beta features."""
    if not beta_header:
        return False
    return "thinking" in beta_header.lower()


def is_reasoning_model(model: str, provider_type: str) -> bool:
    """Check if the model supports reasoning features (thinking/adaptive-thinking)."""
    if provider_type in ("antigravity", "custom"):
        return False
    return any(m in model.lower() for m in ["sonnet-3-7", "sonnet-4-5", "claude-3-7", "opus-4-5"])


def filter_beta_header(beta_header: str, model: str, provider_type: str) -> str:
    """Filter incompatible beta features based on the model and provider."""
    if not beta_header:
        return ""

    beta_parts = [part.strip() for part in beta_header.split(',')]

    if not is_reasoning_model(model, provider_type):
        original_len = len(beta_parts)
        beta_parts = [part for part in beta_parts
                      if 'thinking' not in part.lower() and 'effort' not in part.lower()]
        if len(beta_parts) != original_len:
            logger.info(f"[Proxy] Stripped reasoning beta features for non-reasoning model/provider: {model} ({provider_type})")

    return ','.join(beta_parts)


def _sanitize_for_custom_provider(body_json: dict) -> None:
    """Deep-sanitize request body for custom providers.

    Claude Code adds non-standard fields (cache_control, citations, source, etc.)
    that custom providers like enowX don't support and may reject as 'Malformed'.
    This keeps ONLY standard Anthropic API fields at every level.
    """
    ALLOWED_TOP_KEYS = {
        'model', 'messages', 'system', 'tools', 'tool_choice',
        'max_tokens', 'stream', 'temperature', 'top_p', 'top_k',
        'stop_sequences',
    }
    for key in list(body_json.keys()):
        if key not in ALLOWED_TOP_KEYS:
            del body_json[key]

    if isinstance(body_json.get('system'), list):
        for block in body_json['system']:
            for key in list(block.keys()):
                if key not in ('type', 'text'):
                    del block[key]

    if isinstance(body_json.get('tools'), list):
        ALLOWED_TOOL_KEYS = {'name', 'description', 'input_schema', 'type'}
        for tool in body_json['tools']:
            for key in list(tool.keys()):
                if key not in ALLOWED_TOOL_KEYS:
                    del tool[key]

    ALLOWED_MSG_KEYS = {'role', 'content'}
    ALLOWED_BLOCK_KEYS = {
        'text':        {'type', 'text'},
        'tool_use':    {'type', 'id', 'name', 'input'},
        'tool_result': {'type', 'tool_use_id', 'content', 'is_error'},
        'image':       {'type', 'source'},
    }

    if 'messages' in body_json:
        for msg in body_json['messages']:
            for key in list(msg.keys()):
                if key not in ALLOWED_MSG_KEYS:
                    del msg[key]

            if not isinstance(msg.get('content'), list):
                continue

            for block in msg['content']:
                btype = block.get('type', '')
                allowed = ALLOWED_BLOCK_KEYS.get(btype, {'type'})
                for key in list(block.keys()):
                    if key not in allowed:
                        del block[key]

                if btype == 'tool_use' and isinstance(block.get('input'), str):
                    raw = block['input'].strip()
                    if raw:
                        try:
                            parsed = json.loads(raw)
                            block['input'] = parsed if isinstance(parsed, dict) else {}
                        except json.JSONDecodeError:
                            block['input'] = {}
                    else:
                        block['input'] = {}

                if btype == 'tool_result' and isinstance(block.get('content'), list):
                    for sub in block['content']:
                        if isinstance(sub, dict):
                            sub_type = sub.get('type', '')
                            sub_allowed = ALLOWED_BLOCK_KEYS.get(sub_type, {'type'})
                            for key in list(sub.keys()):
                                if key not in sub_allowed:
                                    del sub[key]


def sanitize_for_custom(body_json: dict) -> bytes:
    """Sanitize and serialize request body for custom providers.

    Strips non-standard Anthropic fields that custom providers reject.
    NEVER drops, truncates, or modifies any messages — all context is preserved.
    """
    _sanitize_for_custom_provider(body_json)
    request_body = json.dumps(body_json, ensure_ascii=False).encode('utf-8')

    system_size = len(json.dumps(body_json.get('system', ''), ensure_ascii=False))
    tools_size = len(json.dumps(body_json.get('tools', []), ensure_ascii=False))
    msgs = body_json.get('messages', [])
    msgs_size = len(json.dumps(msgs, ensure_ascii=False))
    logger.info(
        f"[Custom] Payload breakdown: total={len(request_body)/1024:.0f}KB "
        f"(system={system_size/1024:.0f}KB, tools={tools_size/1024:.0f}KB, "
        f"messages={msgs_size/1024:.0f}KB [{len(msgs)} msgs])"
    )
    return request_body


def _fix_tool_input(obj: dict) -> bool:
    """Fix a single tool_use input if it's a string. Returns True if fixed."""
    if obj.get('type') == 'tool_use' and isinstance(obj.get('input'), str):
        raw = obj['input'].strip()
        if raw:
            try:
                parsed = json.loads(raw)
                obj['input'] = parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                obj['input'] = {}
        else:
            obj['input'] = {}
        return True
    return False


def fix_streaming_tool_inputs(raw_body: bytes) -> bytes:
    """Fix tool_use blocks in SSE responses where 'input' is a string instead of a dict.

    Scans ALL event types (content_block, delta, message.content[])
    for malformed inputs, not just content_block_start events.
    """
    text = raw_body.decode('utf-8', errors='replace')
    lines = text.split('\n')
    output = []
    fix_count = 0

    for line in lines:
        if not line.startswith('data: ') or line.strip() == 'data: [DONE]':
            output.append(line)
            continue
        try:
            event = json.loads(line[6:])

            block = event.get('content_block')
            if isinstance(block, dict) and _fix_tool_input(block):
                fix_count += 1

            delta = event.get('delta')
            if isinstance(delta, dict) and _fix_tool_input(delta):
                fix_count += 1

            message = event.get('message')
            if isinstance(message, dict) and isinstance(message.get('content'), list):
                for cb in message['content']:
                    if isinstance(cb, dict) and _fix_tool_input(cb):
                        fix_count += 1

            output.append('data: ' + json.dumps(event))
        except (json.JSONDecodeError, Exception):
            output.append(line)

    if fix_count:
        logger.info(f"[Custom] Fixed {fix_count} malformed tool_use inputs in response stream")
    return '\n'.join(output).encode('utf-8')
