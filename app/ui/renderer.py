# ui/renderer.py
import markdown
from pathlib import Path

from core.settings import load_theme  # new

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = BASE_DIR / "chat_template.html"

try:
    CHAT_TEMPLATE = TEMPLATE_PATH.read_text(encoding="utf-8")
except Exception:
    CHAT_TEMPLATE = "<!DOCTYPE html><html><body>{{CHAT_CONTENT}}</body></html>"


def _render_markdown(text: str) -> str:
    if not text:
        return ""
    return markdown.markdown(
        text,
        extensions=["tables", "fenced_code"],
    )


def _escape_html(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def wrap_page(chat_html: str) -> str:
    # $ Inject theme colors + chat content into outer template
    theme = load_theme()
    page = CHAT_TEMPLATE

    replacements = {
        "{{COLOR_BG}}": theme.get("bg", "#111111"),
        "{{COLOR_FG}}": theme.get("fg", "#eeeeee"),
        "{{COLOR_LINK}}": theme.get("link", "#6cf"),
        "{{COLOR_USER_BUBBLE_BG}}": theme.get("user_bubble_bg", "#1b2836"),
        "{{COLOR_SYSTEM_TEXT}}": theme.get("system_text", "#888888"),
        "{{COLOR_CODE_BG}}": theme.get("code_bg", "#1e1e1e"),
        "{{COLOR_TABLE_BORDER}}": theme.get("table_border", "#555555"),
        "{{COLOR_TABLE_HEADER_BG}}": theme.get("table_header_bg", "#222222"),
        "{{COLOR_BLOCKQUOTE_BORDER}}": theme.get("blockquote_border", "#666666"),
        "{{COLOR_SCROLLBAR_TRACK}}": theme.get("scrollbar_track", "#111111"),
        "{{COLOR_SCROLLBAR_THUMB}}": theme.get("scrollbar_thumb", "#444444"),
        "{{COLOR_SCROLLBAR_THUMB_HOVER}}": theme.get("scrollbar_thumb_hover", "#666666"),
    }

    for k, v in replacements.items():
        page = page.replace(k, v)

    return page.replace("{{CHAT_CONTENT}}", chat_html or "")


def render_system_msg(content: str) -> str:
    safe = _escape_html(content)
    return (
        "<div class='msg msg-system'>"
        f"<pre>{safe}</pre>"
        "</div>"
    )


def render_user_msg(content: str) -> str:
    body = _render_markdown(content)
    if not body:
        body = "<em>(empty)</em>"
    return "<div class='msg msg-user'>" f"{body}" "</div>"


def render_assistant_msg(reasoning: str, answer: str) -> str:
    body = _render_markdown(answer)
    if not body:
        body = "<em>(empty)</em>"
    return "<div class='msg msg-assistant'>" f"{body}" "</div>"


def render_web_links_block(content: str) -> str:
    body = _render_markdown(content or "Web search sources: (none)")
    return (
        "<div class='msg msg-assistant'>"
        "<details class='web-results'>"
        "<summary>Show web search sources</summary>"
        f"{body}"
        "</details>"
        "</div>"
    )
