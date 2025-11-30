# LocalChat – Local LLM + Web Search Desktop Client

A PyQt-based desktop chat client for local LLMs (via Ollama) with optional web search using a self-hosted SearXNG instance.


## Requirements

- **OS**: Linux (primary target), should also work on macOS/Windows with minor tweaks.
- **Python**: 3.10+ recommended.
- **Local LLM backend**: [Ollama](https://ollama.com/) running locally.  
  Default endpoint: `http://127.0.0.1:11434`
- **Web search backend** (optional): [SearXNG](https://docs.searxng.org/) accessible over HTTP.  
  Default endpoint used by the app: `http://127.0.0.1:8888/search` (configurable in `app/web/searx_client.py`).

### Python packages

Install these via `pip`:

```bash
pip install \
  PyQt5 \
  PyQtWebEngine \
  requests \
  markdown \
  beautifulsoup4
```

If you use a virtualenv (recommended), see below.

---

## Setup

### 1. Clone the repository

```bash
cd /home/seb/Documents/coding
git clone https://github.com/sebastianszewc/localchat.git
cd localchat
```

(Adjust the path if you keep it somewhere else.)

### 2. Create and activate a virtual environment (optional but recommended)

```bash
python -m venv venv
source venv/bin/activate      # on Linux / macOS
# .\venv\Scripts\activate  # on Windows PowerShell
```

### 3. Install Python dependencies

From the repo root:

```bash
pip install \
  PyQt5 \
  PyQtWebEngine \
  requests \
  markdown \
  beautifulsoup4
```


## Ollama setup (local LLM)

1. Install Ollama  
   Follow instructions on https://ollama.com for your OS.

2. Start Ollama daemon (usually auto-starts):

   ```bash
   ollama serve
   ```

3. Pull at least one model, e.g.:

   ```bash
   ollama pull llama3
   # or any other model you want to use as your DEFAULT_MODEL_NAME
   ```

4. The app expects Ollama at:

   ```text
   http://127.0.0.1:11434
   ```

   This is controlled in `app/core/backend.py`:

   ```python
   OLLAMA_BASE = "http://127.0.0.1:11434"
   API_URL = f"{OLLAMA_BASE}/api/chat"
   TAGS_URL = f"{OLLAMA_BASE}/api/tags"
   ```

   Change these if your Ollama instance runs elsewhere.

---

## SearXNG via Docker (web search)

The app talks to SearXNG via `app/web/searx_client.py`:

```python
# SearXNG endpoint (Docker usually maps it like: 0.0.0.0:8888->8080/tcp)
SEARX_URL = "http://127.0.0.1:8888/search"
```

You can leave that as-is and run SearXNG in Docker like this:

### 1. Run SearXNG container

```bash
docker run -d \
  --name searxng \
  -p 8888:8080 \
  searxng/searxng
```

This will:

- Start SearXNG in the background.
- Expose it on `http://127.0.0.1:8888/`.

The app will call `http://127.0.0.1:8888/search?...` for meta-search.

### 2. Basic SearXNG config (optional)

For a more persistent setup you can:

- Create a local config directory, e.g. `~/searxng/settings.yml`.

- Run SearXNG with a bind mount:

  ```bash
  mkdir -p ~/searxng
  # copy or create your settings.yml in ~/searxng
  
  docker run -d \
    --name searxng \
    -p 8888:8080 \
    -v ~/searxng:/etc/searxng \
    searxng/searxng
  ```

Refer to the official docs for advanced config (engines, filters, etc.).

### 3. Point the app to a different SearXNG instance (optional)

If your SearXNG is not at `127.0.0.1:8888`:

- Edit `app/web/searx_client.py`:

  ```python
  SEARX_URL = "http://your-searxng-host:port/search"
  ```

- Restart the app.

---

## Running the app

From the repo root:

```bash
cd app
python main.py
```

Or, if you prefer using the module path from the root of the repo:

```bash
# from /home/seb/Documents/coding/localchat
python -m app.main
```

### Flow

On launch, the app:

- Loads models from Ollama (`/api/tags`).
- Loads settings from `app/data/settings.json`.
- Loads chat history from `app/data/chats.json` (if present).

You can:

- Choose a model in the top bar.
- Toggle **Search web** to use SearXNG + web context.
- Open **Settings** to configure prompts, themes, web search behavior, and auto chat titles.

---

## Configuration files

Located in `app/data/`:

- `settings.json` – UI + behavior (default model, theme, web search options, auto title planner toggle, etc.).
- `chats.json` – chat history.
- `theme_presets.json` – named color themes for the UI.
- `prompts.json` – overrides for system / planner prompts (if you choose to customize them).

It’s safe to delete `chats.json` and `settings.json` to reset history + settings (the app will recreate them with defaults).

---

## Development notes

- Main window: `app/window.py` (`HttpLLMChatWindow`).
- Backend LLM worker: `app/core/backend.py` (`Worker`).
- Web search logic:
  - Planner: `app/web/search_planner.py`
  - SearXNG client: `app/web/searx_client.py`
  - Orchestrator: `app/web/web_search.py` (`WebSearchWorker`)
- HTML rendering / UI template:
  - `app/ui/chat_template.html`
  - `app/ui/renderer.py`
  - `app/ui/style.qss`
- Settings overlay: `app/ui/settings_window.py`.

---

## Troubleshooting

- **Window opens but no models appear**  
  Check that Ollama is running and reachable at `http://127.0.0.1:11434`. Try:

  ```bash
  curl http://127.0.0.1:11434/api/tags
  ```

- **Web search fails**  
  Ensure SearXNG is up:

  ```bash
  curl "http://127.0.0.1:8888/search?q=test"
  ```

  If it isn’t, start the container again or adjust `SEARX_URL` in `searx_client.py`.

