# searx_client.py
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any

# SearXNG endpoint (Docker usually maps it like: 0.0.0.0:8888->8080/tcp)
SEARX_URL = "http://127.0.0.1:8888/search"


# Raised when the SearXNG request fails.
class SearchError(Exception):
    pass


# Call SearXNG and return a list of dicts:
# {
#     "title": str,
#     "url": str,
#     "snippet": str,
# }

def search_web(
    query: str,
    num_results: int = 10,
    timeout: int = 15,
    language: str = "en",
    safesearch: int = 1,
    categories: str = "general",
) -> List[Dict[str, Any]]:
    if not query:
        raise ValueError("search_web() got empty query")

    params = {
        "q": query,
        "format": "json",
    }

    # Language: "auto" means do not send param -> SearX default
    if language and language != "auto":
        params["language"] = language

    # Safe search
    if safesearch is not None:
        try:
            params["safesearch"] = int(safesearch)
        except Exception:
            params["safesearch"] = 1

    # Categories
    if categories:
        params["categories"] = categories

    try:
        resp = requests.get(SEARX_URL, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise SearchError(f"SearXNG request failed: {e}") from e

    raw_results = data.get("results") or []
    results: List[Dict[str, Any]] = []

    for item in raw_results:
        title = (item.get("title") or "").strip()
        url = (item.get("url") or "").strip()
        snippet = (item.get("content") or item.get("snippet") or "").strip()

        if not url:
            continue

        results.append(
            {
                "title": title or url,
                "url": url,
                "snippet": snippet,
            }
        )

        if len(results) >= num_results:
            break

    return results



# Fetch a page and return plain text (no HTML), truncated to max_chars.
# Non-HTML content is ignored.
def fetch_page_text(url: str, max_chars: int = 8000, timeout: int = 15) -> str:
    if not url:
        return ""

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; LocalLLM/0.1)"
        }
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
    except Exception:
        return ""

    content_type = resp.headers.get("content-type", "")
    if "text/html" not in content_type:
        return ""

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = " ".join(chunk.strip() for chunk in soup.stripped_strings)
    if not text:
        return ""

    if max_chars is not None and max_chars > 0 and len(text) > max_chars:
        text = text[:max_chars] + " …"

    return text
