from datetime import datetime, timedelta

from crewai_tools import SerperDevTool

from services.cache import cache_get, cache_set

_search_tool = None


def _tool() -> SerperDevTool:
    global _search_tool
    if _search_tool is None:
        _search_tool = SerperDevTool()
    return _search_tool


def is_direct_listing(url: str) -> bool:
    direct = ["/jobs/view/", "/job/detail/", "/viewjob", "/job/view/"]
    search = ["/jsearch/", "jobs?q=", "jobs?l=", "/jobs/search"]
    return any(d in url for d in direct) and not any(s in url for s in search)


def search_jobs(role: str, location: str, max_jobs: int = 5, days_back: int = 30) -> list[dict]:
    """Return up to `max_jobs` listings, preferring direct job-view URLs."""
    cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    search_key = f"{role}|{location}|{cutoff}"

    raw_results = cache_get("search", search_key)
    if raw_results is None:
        raw_results = _tool().run(
            search_query=(
                f"{role} job {location} "
                f"site:rozee.pk OR site:indeed.com.pk OR site:linkedin.com after:{cutoff}"
            )
        )
        cache_set("search", search_key, raw_results)

    organic = raw_results.get("organic", []) if isinstance(raw_results, dict) else []
    all_results = [
        {"title": i.get("title", ""), "url": i.get("link", ""), "snippet": i.get("snippet", "")}
        for i in organic
    ]
    direct = [r for r in all_results if is_direct_listing(r["url"])]
    others = [r for r in all_results if not is_direct_listing(r["url"])]
    return (direct + others)[:max_jobs]
