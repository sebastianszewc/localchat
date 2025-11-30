# web_search.py

from PyQt5.QtCore import QObject, pyqtSignal
from web.searx_client import search_web, fetch_page_text
from web.search_planner import build_search_query
from core.settings import load_web_settings


class WebSearchWorker(QObject):
    # $ Signals: raw_message, search_query, md_block, context_blocks
    finished = pyqtSignal(str, str, str, list)
    error = pyqtSignal(str)

    def __init__(self, planner_history, raw_message, model_name, parent=None):
        super().__init__(parent)
        self.planner_history = planner_history or []
        self.raw_message = raw_message or ""
        self.model_name = model_name

    def run(self):
        try:
            # Load web search settings each run (so changes in settings take effect)
            ws = load_web_settings()

            use_planner = bool(ws.get("use_planner", True))
            max_results = int(ws.get("max_results", 10))
            max_pages = int(ws.get("max_pages", 5))
            max_chars_per_page = int(ws.get("max_chars_per_page", 6000))
            language = ws.get("language", "en") or "en"
            safesearch = int(ws.get("safesearch", 1))

            # 1) Build search query (planner or raw)
            if use_planner:
                try:
                    search_query = build_search_query(
                        self.planner_history,
                        self.raw_message,
                        self.model_name,
                    )
                except Exception:
                    # Fallback: use raw user text directly
                    search_query = self.raw_message
            else:
                search_query = self.raw_message

            # 2) Run SearXNG
            results = search_web(
                search_query,
                num_results=max_results,
                language=language,
                safesearch=safesearch,
                # categories is left as SearX default ("general")
            )
            if not results:
                self.error.emit("Web search returned no results.")
                return

            # 3) Fetch page text + build markdown + context blocks
            md_lines = []
            context_blocks = []

            for i, item in enumerate(results[:max_pages], start=1):
                title = (item.get("title") or "").strip() or f"Result {i}"
                url = (item.get("url") or "").strip()
                snippet = (item.get("snippet") or "").strip()

                page_text = ""
                if url:
                    page_text = fetch_page_text(url, max_chars=max_chars_per_page) or ""

                # Markdown shown to the user
                if url:
                    md_piece = f"{i}. [{title}]({url})"
                else:
                    md_piece = f"{i}. {title}"

                if snippet:
                    md_piece += f"\n{snippet}"

                if page_text:
                    excerpt = page_text[:400].replace("\n", " ")
                    md_piece += "\n\n> " + excerpt

                md_lines.append(md_piece)

                # Plain text block fed to the model
                block_lines = [
                    f"Result {i}: {title}",
                    f"URL: {url}",
                ]
                if snippet:
                    block_lines.append(f"Snippet: {snippet}")
                if page_text:
                    block_lines.append("Content:")
                    block_lines.append(page_text)

                context_blocks.append("\n".join(block_lines))

            if md_lines:
                md_block = "\n\n---\n\n".join(md_lines)
            else:
                md_block = "_no results_"

            self.finished.emit(self.raw_message, search_query, md_block, context_blocks)

        except Exception as e:
            self.error.emit(str(e))
