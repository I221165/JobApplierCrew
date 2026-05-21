from crewai_tools import ScrapeWebsiteTool

from services.cache import cache_get, cache_set

_scrape_tool = None


def _tool() -> ScrapeWebsiteTool:
    global _scrape_tool
    if _scrape_tool is None:
        _scrape_tool = ScrapeWebsiteTool()
    return _scrape_tool


def scrape_job(url: str, max_chars: int = 5000) -> str:
    """Scrape a job page, returning at most `max_chars` of text. Cached by URL."""
    cached = cache_get("scrape", url)
    if cached:
        return cached["text"]

    content = _tool().run(website_url=url)
    text = str(content)[:max_chars]
    cache_set("scrape", url, {"text": text})
    return text
