# core/chat_state.py
import json
from pathlib import Path

from .backend import DEFAULT_MODEL_NAME
from .settings import get_system_prompt



# app/ directory
BASE_DIR = Path(__file__).resolve().parent.parent

# app/data/
DATA_DIR = BASE_DIR / "data"
CHAT_SAVE_PATH = DATA_DIR / "chats.json"


def make_new_chat(title: str, model_name: str = None) -> dict:
    # $ Create a new chat dict with a chosen model
    model = (model_name or DEFAULT_MODEL_NAME).strip()
    if not model:
        model = DEFAULT_MODEL_NAME

    return {
        "title": title,
        "model": model,
        "history": [
            {"role": "system", "content": get_system_prompt()},
        ],
        "html": "",
    }


def _shrink_web_results(content: str) -> str:
    # $ Take the huge web_results blob and keep only title+URL pairs as markdown links.
    lines = (content or "").splitlines()
    links = []

    current_title = None
    for line in lines:
        line = line.strip()
        if line.startswith("Result ") and ": " in line:
            # e.g. "Result 1: 200 Best Dad Jokes..."
            current_title = line.split(": ", 1)[1].strip()
        elif line.startswith("URL: ") and current_title:
            url = line[5:].strip()
            if url:
                links.append(f"- [{current_title}]({url})")
            current_title = None

    if not links:
        return "Web search sources: (none)"

    return "Web search sources:\n\n" + "\n".join(links)


def save_chats(chats: list, current_index: int) -> None:
    # $ Save chats + current index, compressing web_results to links-only
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        clean_chats = []
        for chat in chats:
            raw_history = chat.get("history", [])
            new_history = []

            for msg in raw_history:
                kind = (msg.get("kind") or "").strip()
                if kind == "web_results":
                    # $ compress this giant blob to only hyperlinks
                    content = msg.get("content") or ""
                    msg = msg.copy()
                    msg["content"] = _shrink_web_results(content)
                    # optionally re-label
                    msg["kind"] = "web_links"

                new_history.append(msg)

            clean_chats.append({
                "title": chat.get("title", ""),
                "model": chat.get("model", DEFAULT_MODEL_NAME),
                "history": new_history,
            })

        data = {
            "chats": clean_chats,
            "current_index": current_index,
        }

        CHAT_SAVE_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        print("Error saving chats:", e)



def load_chats():
    if not CHAT_SAVE_PATH.exists():
        return None

    try:
        raw = CHAT_SAVE_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        chats = data.get("chats", [])
        current_index = data.get("current_index", 0)

        if not chats:
            return None

        # $ one-time cleanup: drop old web_results messages
        for chat in chats:
            hist = chat.get("history", [])
            chat["history"] = [
                m for m in hist
                if (m.get("kind") or "") != "web_results"
            ]

        current_index = max(0, min(current_index, len(chats) - 1))
        return chats, current_index
    except Exception as e:
        print("Error loading chats:", e)
        return None
