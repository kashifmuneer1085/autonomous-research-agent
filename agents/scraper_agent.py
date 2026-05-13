"""
agents/scraper_agent.py
-----------------------
Scraper Agent

Responsibilities:
  1. Accept a list of URLs.
  2. Scrape each URL concurrently (httpx → Playwright fallback).
  3. Filter pages with insufficient content.
  4. Return a {url: text} mapping of successfully scraped content.

Delegates all low-level scraping to utils.scraper_utils.
"""

from __future__ import annotations

from typing import Any, Optional

from utils.scraper_utils import scrape_urls_parallel
from utils.text_processing import clean_text
from core.config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

_MIN_TEXT_LENGTH = 300  # Characters — discard pages below this


class ScraperAgent:
    """
    Agent 3 — Scraper

    Concurrently fetches and extracts text from all candidate URLs.
    """

    async def run(self, urls: list[str]) -> dict[str, Any]:
        """
        Parameters
        ----------
        urls : list[str]
            Candidate URLs from SearchAgent.

        Returns
        -------
        dict with keys:
          - scraped_content : dict[str, str]  {url: cleaned_text}
          - successful : int
          - failed : int
        """
        if not urls:
            logger.warning("scraper_agent_empty_input")
            return {"scraped_content": {}, "successful": 0, "failed": 0}

        logger.info("scraper_agent_start", num_urls=len(urls))

        # Parallel scrape
        raw_results: dict[str, Optional[str]] = await scrape_urls_parallel(urls)

        # Filter and clean
        scraped_content: dict[str, str] = {}
        failed = 0

        for url, raw_text in raw_results.items():
            if not raw_text or len(raw_text.strip()) < _MIN_TEXT_LENGTH:
                logger.debug("scraper_skip_empty", url=url)
                failed += 1
                continue

            cleaned = clean_text(raw_text)
            scraped_content[url] = cleaned
            logger.debug("scraper_success", url=url, chars=len(cleaned))

        successful = len(scraped_content)
        logger.info(
            "scraper_agent_complete",
            successful=successful,
            failed=failed,
        )

        return {
            "scraped_content": scraped_content,
            "successful": successful,
            "failed": failed,
        }
