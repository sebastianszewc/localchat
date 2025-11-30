# web/search_planner.py
import requests

from core.backend import API_URL, DEFAULT_MODEL_NAME, N_PREDICT
from core.settings import get_search_planner_prompt


def _format_conversation(conversation_history, max_chars: int = 8000) -> str:
    """Turn the history into a simple transcript:
       You: ...
       Model: ...
    """
    if not conversation_history:
        return ""

    lines = []
    for msg in conversation_history:
        role = (msg.get("role") or "").lower()
        content = (msg.get("content") or "").strip()
        if not content:
            continue

        if role == "user":
            prefix = "You"
        elif role == "assistant":
            prefix = "Model"
        else:
            continue

        lines.append(f"{prefix}: {content}")

    txt = "\n".join(lines)
    if len(txt) > max_chars:
        txt = txt[-max_chars:]
    return txt


def build_search_query(conversation_history, latest_user_text: str, model_name: str = None) -> str:
    """
    Build a single best search query using the same model + API as main chat.
    """
    latest_user_text = (latest_user_text or "").strip()
    if not latest_user_text:
        return ""

    planner_model = (model_name or DEFAULT_MODEL_NAME).strip() or DEFAULT_MODEL_NAME
    transcript = _format_conversation(conversation_history)

    user_prompt = get_search_planner_prompt().format(TRANSCRIPT=transcript)

    messages = [
        {
            "role": "user",
            "content": user_prompt,
        }
    ]

    payload = {
        "model": planner_model,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {
            "num_predict": N_PREDICT,
            "temperature": 0.7,
            "top_p": 0.9,
            "repeat_penalty": 1.1,
        },
    }

    try:
        r = requests.post(API_URL, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[search_planner] ERROR request failed: {e}")
        # If anything goes wrong, just search with the user’s last text.
        return latest_user_text

    msg = data.get("message") or {}
    raw_content = (msg.get("content") or "").strip()

    # For debugging: print whatever the planner actually returned
    print("[search_planner] RAW:", repr(raw_content))

    # If the planner gave nothing, fall back to the last user text
    if not raw_content:
        return latest_user_text

    return raw_content
