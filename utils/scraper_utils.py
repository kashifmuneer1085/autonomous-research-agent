"""
utils/scraper_utils.py
----------------------
Low-level scraping primitives used by the Scraper Agent.

Strategy:
  1. Try lightweight httpx fetch first (fast, no JS).
  2. Fall back to Playwright if the page is JS-rendered or returns empty content.

Content extraction via BeautifulSoup targets <article>, <main>, <p> tags and
strips navigation, ads, scripts, and styles.
"""

import asyncio
import re
from typing import Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from core.config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_JUNK_TAGS = ["script", "style", "nav", "header", "footer",
              "aside", "noscript", "iframe", "form", "button"]

_MIN_CONTENT_LENGTH = 200  # Discard pages shorter than this


# ── HTML → Text Extraction ────────────────────────────────────────────────────

def extract_text_from_html(html: str, url: str = "") -> str:
    """
    Parse *html* with BeautifulSoup and extract human-readable text.

    Priority order for main content:
      <article> → <main> → <div role="main"> → <body>
    """
    soup = BeautifulSoup(html, "lxml")

    # Remove junk tags in-place
    for tag in soup((_JUNK_TAGS)):
        tag.decompose()

    # Find the most likely content container
    content_node = (
        soup.find("article")
        or soup.find("main")
        or soup.find("div", role="main")
        or soup.find("div", class_=re.compile(r"(content|article|post|entry)", re.I))
        or soup.body
    )

    if content_node is None:
        return ""

    # Extract text preserving paragraph breaks
    paragraphs = []
    for elem in content_node.find_all(["p", "h1", "h2", "h3", "h4", "li"]):
        text = elem.get_text(separator=" ", strip=True)
        if text and len(text) > 30:  # Filter stub fragments
            paragraphs.append(text)

    raw = "\n\n".join(paragraphs)

    # Also capture the page title
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""
    if title:
        raw = f"# {title}\n\n{raw}"

    return raw[:settings.MAX_CONTENT_LENGTH]


# ── HTTP Fetch (fast path) ────────────────────────────────────────────────────

@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    stop=stop_after_attempt(settings.MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
async def fetch_with_httpx(url: str) -> Optional[str]:
    """
    Fetch a URL with httpx (no JS execution).
    Returns extracted text or None on failure.
    """
    try:
        async with httpx.AsyncClient(
            headers=_HEADERS,
            timeout=settings.SCRAPER_TIMEOUT_S,
            follow_redirects=True,
            verify=False,  # Tolerate self-signed certs
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text
            text = extract_text_from_html(html, url)
            if len(text) >= _MIN_CONTENT_LENGTH:
                logger.debug("httpx_fetch_success", url=url, chars=len(text))
                return text
            logger.debug("httpx_content_too_short", url=url, chars=len(text))
            return None
    except Exception as exc:
        logger.warning("httpx_fetch_failed", url=url, error=str(exc))
        return None


# ── Playwright Fetch (JS fallback) ───────────────────────────────────────────

async def fetch_with_playwright(url: str) -> Optional[str]:
    """
    Fetch a URL with Playwright (full browser, handles SPAs and lazy-loaded content).
    Falls back to this when httpx yields too-short content.
    """
    try:
        from playwright.async_api import async_playwright  # Lazy import

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=_HEADERS["User-Agent"],
                ignore_https_errors=True,
            )
            page = await context.new_page()
            await page.goto(url, timeout=settings.SCRAPER_TIMEOUT_S * 1000,
                            wait_until="domcontentloaded")
            # Wait for network to quiet down
            await page.wait_for_timeout(1500)
            html = await page.content()
            await browser.close()

        text = extract_text_from_html(html, url)
        if len(text) >= _MIN_CONTENT_LENGTH:
            logger.debug("playwright_fetch_success", url=url, chars=len(text))
            return text

        logger.warning("playwright_content_too_short", url=url, chars=len(text))
        return None

    except Exception as exc:
        logger.warning("playwright_fetch_failed", url=url, error=str(exc))
        return None


# ── Public Entry Point ────────────────────────────────────────────────────────

async def scrape_url(url: str) -> Optional[str]:
    """
    Scrape *url* using the two-stage strategy:
      1. httpx (fast, low resource)
      2. Playwright (full browser, JS support)

    Returns cleaned text content or None if both methods fail.
    """
    # Skip non-HTTP URLs (PDFs handled separately, mailto: etc.)
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return None

    # Skip PDF links (could add PDF extraction here in the future)
    if url.lower().endswith(".pdf"):
        logger.info("skipping_pdf", url=url)
        return None

    text = await fetch_with_httpx(url)
    if text:
        return text

    logger.info("falling_back_to_playwright", url=url)
    return await fetch_with_playwright(url)


async def scrape_urls_parallel(urls: list[str]) -> dict[str, Optional[str]]:
    """
    Scrape multiple URLs concurrently, respecting SCRAPER_CONCURRENCY.
    Returns {url: text_or_None} mapping.
    """
    semaphore = asyncio.Semaphore(settings.SCRAPER_CONCURRENCY)

    async def _bounded_scrape(url: str) -> tuple[str, Optional[str]]:
        async with semaphore:
            text = await scrape_url(url)
            return url, text

    tasks = [_bounded_scrape(u) for u in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    output: dict[str, Optional[str]] = {}
    for item in results:
        if isinstance(item, Exception):
            logger.error("parallel_scrape_error", error=str(item))
        else:
            url, text = item
            output[url] = text

    successful = sum(1 for v in output.values() if v)
    logger.info("parallel_scrape_done", total=len(urls), successful=successful)
    return output
