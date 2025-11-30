# core/chat_title.py

from typing import List, Dict, Any
import requests
from core.backend import API_URL, DEFAULT_MODEL_NAME
from core.settings import get_title_planner_prompt


def _get_first_user_message(history: List[Dict[str, Any]]) -> str:
    # Return the first non-empty user message from the history.
    if not history:
        return ""
    for msg in history:
        role = (msg.get("role") or "").lower()
        if role != "user":
            continue
        content = (msg.get("content") or "").strip()
        if content:
            return content
    return ""


def _fallback_title(first_msg: str) -> str:
    # Very simple fallback: use the first user message, first line only, truncated.
    if not first_msg:
        return "New chat"
    text = first_msg.strip().splitlines()[0]
    if len(text) > 80:
        text = text[:80].rstrip()
    return text or "New chat"


def _extract_content_from_response(data: Any) -> str:
    """
    Try to pull the assistant text from several common API formats:

    - OpenAI / OpenWebUI: data["choices"][0]["message"]["content"]
    - OpenAI text completion: data["choices"][0]["text"]
    - Ollama /api/chat: data["message"]["content"]
    - Ollama /api/generate or similar: data["response"]
    """
    if not isinstance(data, dict):
        return ""

    # OpenAI / OpenWebUI chat-style
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        c0 = choices[0] or {}
        msg = c0.get("message") or {}
        txt = (
            msg.get("content")
            or c0.get("text")  # text-completion fallback
            or ""
        )
        if txt:
            return str(txt)

    # Ollama chat: {"message": {"role": "...", "content": "..."}}
    msg = data.get("message")
    if isinstance(msg, dict):
        txt = msg.get("content")
        if txt:
            return str(txt)

    # Ollama generate: {"response": "..."}
    if data.get("response"):
        return str(data["response"])

    return ""


def build_chat_title(conversation_history, model_name: str | None = None) -> str:
    first_msg = _get_first_user_message(conversation_history)
    if not first_msg:
        return ""

    planner_model = (model_name or DEFAULT_MODEL_NAME).strip() or DEFAULT_MODEL_NAME

    template = get_title_planner_prompt()
    user_prompt = template.format(
        FIRST_MESSAGE=first_msg,
        first_message=first_msg,
    )

    messages = [
        {"role": "user", "content": user_prompt}
    ]

    # Use a generic "chat completions" style payload.
    # This works with OpenWebUI / OpenAI-compatible backends.
    payload = {
        "model": planner_model,
        "messages": messages,
        # Most backends default to non-streaming; stream flag is safe.
        "stream": False,
        # Generic sampling parameters.
        "temperature": 0.5,
        "top_p": 0.9,
        # Use max_tokens / num_predict depending on backend; many
        # OpenAI-style servers accept max_tokens, Ollama ignores it.
        "max_tokens": 64,
    }

    try:
        r = requests.post(API_URL, json=payload, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[title_planner] ERROR request failed: {e}")
        return _fallback_title(first_msg)

    raw_content = _extract_content_from_response(data).strip()
    print("[title_planner] RAW OUTPUT:", repr(raw_content))

    if not raw_content:
        return _fallback_title(first_msg)

    # Very light post-processing: single line, trimmed, without wrapping quotes
    title = raw_content.replace("\n", " ").strip()

    # Strip surrounding quotes, if the model ignored instructions
    if (title.startswith('"') and title.endswith('"')) or (
        title.startswith("'") and title.endswith("'")
    ):
        title = title[1:-1].strip()

    # Enforce length constraints
    if len(title) > 80:
        title = title[:80].rstrip()

    return title or _fallback_title(first_msg)
