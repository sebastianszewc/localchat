# backend.py
import requests
from PyQt5.QtCore import QObject, pyqtSignal

# Ollama HTTP API base
OLLAMA_BASE = "http://127.0.0.1:11434"
API_URL = f"{OLLAMA_BASE}/api/chat"
TAGS_URL = f"{OLLAMA_BASE}/api/tags"

# Generation limits (used for normal chat)
MAX_TOKENS = 2048
N_PREDICT = 2048


# Ask Ollama for all installed models via /api/tags (GET).
# Returns a list of model names like: ['mistral:latest', 'llama3:8b', ...]
def get_available_models():
    try:
        r = requests.get(TAGS_URL, timeout=5)
        r.raise_for_status()
        data = r.json()
        models = [m.get("name") for m in data.get("models", []) if m.get("name")]
        return models or ["llama3:latest"]
    except Exception as e:
        print("ERROR fetching models from Ollama:", e)
        return ["llama3:latest"]


AVAILABLE_MODELS = get_available_models()
DEFAULT_MODEL_NAME = AVAILABLE_MODELS[0]


class Worker(QObject):
    # Background worker that sends the current chat history to Ollama
    # and emits (reasoning, content) when done.
    # Reasoning is always empty here; only the main reply is used.
    finished = pyqtSignal(str, str)  # (reasoning, content)
    error = pyqtSignal(str)

    def __init__(self, history, model_name, parent=None):
        super().__init__(parent)
        self.history = history or []
        self.model_name = model_name or DEFAULT_MODEL_NAME

    # Perform the blocking HTTP request to Ollama and emit signals when done.
    def run(self):
        try:
            # Normalize history into Ollama message format
            messages = []
            for item in self.history:
                role = item.get("role", "user")
                content = item.get("content", "")

                if role not in ("system", "user", "assistant"):
                    role = "user"

                messages.append(
                    {
                        "role": role,
                        "content": content,
                    }
                )

            payload = {
                "model": self.model_name,
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

            r = requests.post(API_URL, json=payload, timeout=600)
            r.raise_for_status()
            data = r.json()

            msg = data.get("message") or {}
            content = (msg.get("content") or "").strip()

            reasoning = ""
            self.finished.emit(reasoning, content)

        except Exception as e:
            self.error.emit(str(e))
