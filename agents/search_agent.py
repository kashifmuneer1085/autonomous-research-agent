"""
agents/search_agent.py
----------------------
Search Agent — powered by DuckDuckGo (FREE, no API key needed)

Responsibilities:
  1. Accept a list of search query strings.
  2. Execute each query against DuckDuckGo (no key required).
  3. Deduplicate and rank URLs by source credibility score.
  4. Return the top-N URLs for scraping.

Uses the duckduckgo-search Python library — completely free, no signup needed.
"""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlparse

from ddgs import DDGS

from core.config import settings
from utils.logger import get_logger
from utils.text_processing import score_source_credibility

logger = get_logger(__name__)

# Domains to exclude (login walls, irrelevant aggregators)
_BLOCKED_DOMAINS = {
    "facebook.com", "twitter.com", "x.com", "instagram.com",
    "linkedin.com", "pinterest.com", "tiktok.com",
    "amazon.com", "ebay.com", "etsy.com",
}


class SearchAgent:
    """
    Agent 2 — Search

    Fetches URLs from DuckDuckGo for multiple search queries
    and ranks them by credibility. Completely free, no API key needed.
    """

    def __init__(self) -> None:
        self.max_results = settings.MAX_SEARCH_RESULTS
        self.max_sources = settings.MAX_SOURCES

    # ── DuckDuckGo Search ─────────────────────────────────────────────────────

    def _ddg_search(self, query: str) -> list[dict[str, str]]:
        """
        Run a synchronous DuckDuckGo search and return results.
        DuckDuckGo library is sync-only so we run it in a thread.
        """
        try:
            with DDGS() as ddgs:
                raw = list(ddgs.text(
                    query,
                    max_results=self.max_results,
                    safesearch="moderate",
                ))
            results = []
            for r in raw:
                results.append({
                    "url": r.get("href", ""),
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                })
            logger.debug("ddg_results", query=query, count=len(results))
            return results
        except Exception as exc:
            logger.warning("ddg_search_error", query=query, error=str(exc))
            return []

    async def _search_single_query(self, query: str) -> list[dict[str, str]]:
        """Run DuckDuckGo search in a thread pool to avoid blocking the event loop."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._ddg_search, query)

    # ── Filtering & Ranking ───────────────────────────────────────────────────

    def _is_valid_url(self, url: str) -> bool:
        if not url:
            return False
        parsed = urlparse(url.lower())
        if parsed.scheme not in ("http", "https"):
            return False
        domain = parsed.netloc.lstrip("www.")
        for blocked in _BLOCKED_DOMAINS:
            if blocked in domain:
                return False
        return True

    def _deduplicate_results(self, all_results: list[dict]) -> list[dict]:
        seen: set[str] = set()
        unique = []
        for r in all_results:
            url = r.get("url", "").rstrip("/")
            if url and url not in seen:
                seen.add(url)
                unique.append(r)
        return unique

    def _score_and_rank(self, results: list[dict]) -> list[dict[str, Any]]:
        scored = []
        for r in results:
            url = r["url"]
            if not self._is_valid_url(url):
                continue
            scored.append({
                "url": url,
                "title": r.get("title", ""),
                "snippet": r.get("snippet", ""),
                "credibility_score": score_source_credibility(url),
            })
        scored.sort(key=lambda x: x["credibility_score"], reverse=True)
        return scored

    # ── Public Entry Point ────────────────────────────────────────────────────

    async def run(self, search_queries: list[str]) -> dict[str, Any]:
        """
        Parameters
        ----------
        search_queries : list[str]
            Query strings from QueryUnderstandingAgent.

        Returns
        -------
        dict with keys:
          - urls : list[str]
          - scored_sources : list[dict]
        """
        logger.info("search_agent_start", num_queries=len(search_queries))

        # Run all queries (small delay between each to be polite to DDG)
        all_results: list[dict] = []
        for query in search_queries:
            results = await self._search_single_query(query)
            all_results.extend(results)
            await asyncio.sleep(1)  # Polite delay for DuckDuckGo

        unique_results = self._deduplicate_results(all_results)
        scored = self._score_and_rank(unique_results)
        top_sources = scored[: self.max_sources]
        urls = [s["url"] for s in top_sources]

        logger.info(
            "search_agent_complete",
            total_raw=len(all_results),
            unique=len(unique_results),
            selected=len(top_sources),
        )

        return {
            "urls": urls,
            "scored_sources": top_sources,
        }
