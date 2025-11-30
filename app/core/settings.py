# core/settings.py
import json
from pathlib import Path
from core.backend import DEFAULT_MODEL_NAME  # adjust import if needed

BASE_DIR = Path(__file__).resolve().parent.parent
SETTINGS_PATH = BASE_DIR / "data" / "settings.json"
THEME_PRESETS_PATH = BASE_DIR / "data" / "theme_presets.json"
PROMPTS_PATH = BASE_DIR / "data" / "prompts.json"


def load_default_model():
    try:
        raw = SETTINGS_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        model = (data.get("default_model") or "").strip()
        return model or DEFAULT_MODEL_NAME
    except Exception:
        return DEFAULT_MODEL_NAME

def save_default_model(model_name: str):
    model_name = (model_name or "").strip()
    if not model_name:
        return

    data = {}
    try:
        if SETTINGS_PATH.exists():
            raw = SETTINGS_PATH.read_text(encoding="utf-8")
            data = json.loads(raw)
    except Exception:
        data = {}

    data["default_model"] = model_name

    try:
        SETTINGS_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        print("Error saving settings:", e)

def load_theme() -> dict:
    # $ Merge DEFAULT_THEME with optional overrides from settings.json["theme"]
    theme = DEFAULT_THEME.copy()

    try:
        if SETTINGS_PATH.exists():
            raw = SETTINGS_PATH.read_text(encoding="utf-8")
            data = json.loads(raw)
            overrides = data.get("theme") or {}
            if isinstance(overrides, dict):
                theme.update(overrides)
    except Exception as e:
        print("Error loading theme:", e)

    return theme

def load_theme_presets() -> dict:
    try:
        if THEME_PRESETS_PATH.exists():
            raw = THEME_PRESETS_PATH.read_text(encoding="utf-8")
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
    except Exception as e:
        print("Error loading theme presets:", e)
    return {}

def load_settings_dict() -> dict:
    try:
        if SETTINGS_PATH.exists():
            raw = SETTINGS_PATH.read_text(encoding="utf-8")
            return json.loads(raw)
    except Exception as e:
        print("Error loading settings:", e)
    return {}

def save_settings_dict(data: dict) -> None:
    try:
        SETTINGS_PATH.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as e:
        print("Error saving settings:", e)

def load_prompts_dict() -> dict:
    if not PROMPTS_PATH.exists():
        return {}
    try:
        raw = PROMPTS_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        print("Error loading prompts:", e)
        return {}

def save_prompts_dict(overrides: dict) -> None:
    try:
        PROMPTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        PROMPTS_PATH.write_text(
            json.dumps(overrides, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as e:
        print("Error saving prompts:", e)

def get_prompt(key: str) -> str:
    prompts = DEFAULT_PROMPTS.copy()
    overrides = load_prompts_dict()
    for k, v in overrides.items():
        if isinstance(v, str):
            prompts[k] = v
    return prompts.get(key, "")

def get_system_prompt() -> str:
    return get_prompt("system")

def get_search_planner_prompt() -> str:
    return get_prompt("search_planner")

def get_web_followup_instruction() -> str:
    return get_prompt("web_followup")

def load_web_settings() -> dict:
    """Return merged web_search settings: defaults overlaid with settings.json."""
    data = load_settings_dict()
    raw = data.get("web_search")
    if not isinstance(raw, dict):
        raw = {}

    merged = DEFAULT_WEB_SEARCH_SETTINGS.copy()
    for k, v in raw.items():
        if k in merged:
            merged[k] = v
    return merged

def save_web_settings(settings: dict) -> None:
    """Write web_search settings back into settings.json."""
    data = load_settings_dict()
    base = DEFAULT_WEB_SEARCH_SETTINGS.copy()
    for k, v in settings.items():
        if k in base:
            base[k] = v
    data["web_search"] = base
    save_settings_dict(data)

def get_title_planner_prompt() -> str:
    return get_prompt("title_planner")

def is_title_planner_enabled() -> bool:
    data = load_settings_dict()
    val = data.get("auto_title_planner")
    if val is None:
        return True  # default ON
    return bool(val)

DEFAULT_PROMPTS = {
    "system": (
        "use the $...$ for equastions. there cannot be any space between the "
        "$ characters and the tips of the equasions"
    ),
    "search_planner": (
        "You are a search query planner.\n\n"
        "Here is the conversation so far:\n\n"
        "{TRANSCRIPT}\n\n"
        "Determine the single best internet search query the user would want to "
        "run right now to help answer their most recent question.\n\n"
        "Respond with ONLY the search query text, nothing else."
    ),
    "web_followup": (
        "You are answering the user based solely on the web search results and "
        "page content above.\n\n"
        "Use only information that is clearly supported by those results. If "
        "the answer is unclear or not present, say that you don't know."
    ),
    "title_planner": (
        "You generate short, descriptive titles for chat conversations.\n"
        "Rules:\n"
        "- Use at most 6 words.\n"
        "- No quotes around the title.\n"
        "- No prefixes like 'Title:' or 'Chat:'.\n"
        "- Make it specific, based on the user's question.\n\n"
        "User's first message:\n"
        "{FIRST_MESSAGE}\n\n"
        "Return ONLY the title, nothing else."
    ),
}

DEFAULT_THEME = {
    "bg": "#111111",
    "fg": "#eeeeee",
    "link": "#6cf",
    "user_bubble_bg": "#1b2836",
    "system_text": "#888888",
    "code_bg": "#1e1e1e",
    "table_border": "#555555",
    "table_header_bg": "#222222",
    "blockquote_border": "#666666",
    "scrollbar_track": "#111111",
    "scrollbar_thumb": "#444444",
    "scrollbar_thumb_hover": "#666666",

    "qt_bg": "#111111",
    "qt_fg": "#eeeeee",
    "qt_accent": "#4a90e2",
    "qt_accent_hover": "#5aa0f2",
    "qt_accent_disabled": "#555555",
    "qt_border": "#333333",

    "qt_sidebar_bg": "#101010",
    "qt_sidebar_selected_bg": "#262626",
    "qt_splitter_bg": "#181818",
    "qt_input_bg": "#121212",

    "qt_button_bg": "#181818",
    "qt_button_hover_bg": "#222222",
    "qt_button_pressed_bg": "#262626",
    "qt_button_disabled_bg": "#141414",
    "qt_button_disabled_fg": "#555555",

    "qt_search_toggle_on_bg": "#2b7a3f",
    "qt_search_toggle_on_hover_bg": "#33994c",

    "qt_checkbox_bg": "#181818",
    "qt_checkbox_checked_bg": "#2b7a3f",

    "qt_scrollbar_bg": "#111111",
    "qt_scrollbar_handle_bg": "#444444"
}

DEFAULT_WEB_SEARCH_SETTINGS = {
    # Global on/off switch for the integration (disables the "Search web" button)
    "enabled": True,

    # Use LLM search planner or raw user text as the query
    "use_planner": True,

    # SearXNG / content limits
    "max_results": 10,
    "max_pages": 5,
    "max_chars_per_page": 6000,

    # SearX parameters
    # "auto" means: do not send language param -> SearX default
    "language": "en",   # "auto" or "en"
    "safesearch": 1,    # 0=off, 1=moderate, 2=strict

    # UI / behavior
    "show_query": True,        # show "[web search query] ..." in chat
    "strict_web_only": True,   # inject "answer only from web results" system prompt
}
