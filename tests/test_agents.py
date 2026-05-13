"""
tests/test_agents.py
--------------------
Unit and integration tests for all agent modules.

Run with:
  pytest tests/ -v

Note: LLM-calling tests require OPENAI_API_KEY to be set.
      Tests that call OpenAI are marked with @pytest.mark.integration
      and are skipped if the key is absent.
"""

from __future__ import annotations

import asyncio
import os
import pytest

# Skip LLM tests if no API key
_HAS_OPENAI = bool(os.environ.get("GROQ_API_KEY"))
integration = pytest.mark.skipif(
    not _HAS_OPENAI,
    reason="GROQ_API_KEY not set — skipping integration test",
)


# ── Text Processing ───────────────────────────────────────────────────────────

class TestTextProcessing:
    def test_clean_text_removes_control_chars(self):
        from utils.text_processing import clean_text
        raw = "Hello\x00World\x1f!\n\n\nExtra blank lines\n\n\nEnd"
        result = clean_text(raw)
        assert "\x00" not in result
        assert "\x1f" not in result
        # Triple blank lines collapsed to double
        assert "\n\n\n" not in result

    def test_chunk_text_returns_non_empty(self):
        from utils.text_processing import chunk_text
        text = "Hello world. " * 200
        chunks = chunk_text(text, chunk_size=500, overlap=50)
        assert len(chunks) > 1
        for c in chunks:
            assert len(c) > 0

    def test_chunk_text_empty_input(self):
        from utils.text_processing import chunk_text
        assert chunk_text("") == []

    def test_deduplicate_removes_near_duplicates(self):
        from utils.text_processing import deduplicate_texts
        texts = [
            "The quick brown fox jumps over the lazy dog.",
            "The quick brown fox jumps over the lazy dog.",   # exact dup
            "Completely different content about Python programming.",
        ]
        result = deduplicate_texts(texts, threshold=0.99)
        assert len(result) == 2

    def test_deduplicate_preserves_unique(self):
        from utils.text_processing import deduplicate_texts
        texts = [
            "AI is transforming healthcare diagnosis globally.",
            "Quantum computing is breaking encryption barriers.",
            "Climate change affects global food security.",
        ]
        result = deduplicate_texts(texts, threshold=0.85)
        assert len(result) == 3

    def test_score_credibility_high(self):
        from utils.text_processing import score_source_credibility
        assert score_source_credibility("https://www.nature.com/articles/abc") == 1.0
        assert score_source_credibility("https://pubmed.ncbi.nlm.nih.gov/123") == 1.0

    def test_score_credibility_low(self):
        from utils.text_processing import score_source_credibility
        score = score_source_credibility("http://someblog.blogspot.com/post")
        assert score <= 0.2

    def test_score_credibility_medium(self):
        from utils.text_processing import score_source_credibility
        score = score_source_credibility("https://example.org/page")
        assert 0.5 <= score <= 0.7


# ── Scraper Utils ─────────────────────────────────────────────────────────────

class TestScraperUtils:
    def test_extract_text_from_html_basic(self):
        from utils.scraper_utils import extract_text_from_html
        html = """
        <html><body>
          <nav>Navigation stuff</nav>
          <article>
            <h1>Test Article</h1>
            <p>This is the main content paragraph with enough words to pass the filter.</p>
            <p>Another important paragraph with substantial information about the topic.</p>
          </article>
          <footer>Footer content</footer>
          <script>var x = 1;</script>
        </body></html>
        """
        text = extract_text_from_html(html)
        assert "Test Article" in text
        assert "main content paragraph" in text
        # Navigation and scripts should be stripped
        assert "Navigation stuff" not in text
        assert "var x = 1" not in text

    def test_extract_text_empty_html(self):
        from utils.scraper_utils import extract_text_from_html
        assert extract_text_from_html("") == ""

    @pytest.mark.asyncio
    async def test_scrape_url_invalid_scheme(self):
        from utils.scraper_utils import scrape_url
        result = await scrape_url("ftp://example.com/file")
        assert result is None

    @pytest.mark.asyncio
    async def test_scrape_url_pdf_skipped(self):
        from utils.scraper_utils import scrape_url
        result = await scrape_url("https://example.com/paper.pdf")
        assert result is None


# ── Query Agent ───────────────────────────────────────────────────────────────

class TestQueryAgent:
    @integration
    @pytest.mark.asyncio
    async def test_run_returns_expected_keys(self):
        from agents.query_agent import QueryUnderstandingAgent
        agent = QueryUnderstandingAgent()
        result = await agent.run("AI tools for medical diagnosis")
        assert "refined_query" in result
        assert "search_queries" in result
        assert isinstance(result["search_queries"], list)
        assert len(result["search_queries"]) >= 1
        assert isinstance(result["refined_query"], str)
        assert len(result["refined_query"]) > 5

    @integration
    @pytest.mark.asyncio
    async def test_run_generates_multiple_queries(self):
        from agents.query_agent import QueryUnderstandingAgent
        agent = QueryUnderstandingAgent()
        result = await agent.run("quantum computing applications")
        assert len(result["search_queries"]) >= 2


# ── Search Agent ──────────────────────────────────────────────────────────────

class TestSearchAgent:
    def test_is_valid_url_blocks_social(self):
        from agents.search_agent import SearchAgent
        agent = SearchAgent()
        assert not agent._is_valid_url("https://www.facebook.com/post/123")
        assert not agent._is_valid_url("https://twitter.com/user/status")
        assert agent._is_valid_url("https://nature.com/articles/abc")

    def test_is_valid_url_requires_http(self):
        from agents.search_agent import SearchAgent
        agent = SearchAgent()
        assert not agent._is_valid_url("ftp://example.com")
        assert not agent._is_valid_url("")

    def test_deduplicate_results(self):
        from agents.search_agent import SearchAgent
        agent = SearchAgent()
        results = [
            {"url": "https://example.com/page", "title": "A"},
            {"url": "https://example.com/page/", "title": "A dup"},  # trailing slash variant
            {"url": "https://other.com/page", "title": "B"},
        ]
        unique = agent._deduplicate_results(results)
        urls = [r["url"] for r in unique]
        assert len(urls) == 2

    def test_score_and_rank_sorts_descending(self):
        from agents.search_agent import SearchAgent
        agent = SearchAgent()
        results = [
            {"url": "http://blogspot.com/post", "title": "Blog"},
            {"url": "https://nature.com/article", "title": "Nature"},
            {"url": "https://example.edu/paper", "title": "Edu"},
        ]
        scored = agent._score_and_rank(results)
        scores = [s["credibility_score"] for s in scored]
        assert scores == sorted(scores, reverse=True)


# ── Content Processor ─────────────────────────────────────────────────────────

class TestContentProcessor:
    @pytest.mark.asyncio
    async def test_run_produces_chunks(self):
        from agents.content_processor import ContentProcessingAgent
        agent = ContentProcessingAgent()

        scraped = {
            "https://example.com/a": "Alpha content. " * 100,
            "https://example.com/b": "Beta content about different topics. " * 80,
        }
        scored_sources = [
            {"url": "https://example.com/a", "credibility_score": 0.9},
            {"url": "https://example.com/b", "credibility_score": 0.6},
        ]

        result = await agent.run(scraped, scored_sources)
        assert "processed_chunks" in result
        assert "deduplicated_chunks" in result
        assert len(result["processed_chunks"]) > 0
        # Each chunk has required fields
        for chunk in result["deduplicated_chunks"]:
            assert "url" in chunk
            assert "chunk" in chunk
            assert "credibility_score" in chunk

    @pytest.mark.asyncio
    async def test_run_empty_input(self):
        from agents.content_processor import ContentProcessingAgent
        agent = ContentProcessingAgent()
        result = await agent.run({}, [])
        assert result["processed_chunks"] == []
        assert result["deduplicated_chunks"] == []


# ── Scraper Agent ─────────────────────────────────────────────────────────────

class TestScraperAgent:
    @pytest.mark.asyncio
    async def test_run_empty_urls(self):
        from agents.scraper_agent import ScraperAgent
        agent = ScraperAgent()
        result = await agent.run([])
        assert result["successful"] == 0
        assert result["scraped_content"] == {}


# ── Storage: Local ────────────────────────────────────────────────────────────

class TestStorageLocal:
    def test_save_local(self, tmp_path, monkeypatch):
        from agents import storage_agent
        monkeypatch.setattr(storage_agent.settings, "DATA_DIR", str(tmp_path))

        path = storage_agent._save_local(
            title="Test Report",
            report_markdown="# Test\n\nContent here.",
            metadata={"title": "Test", "date": "2025-01-01", "word_count": 5},
        )
        assert Path(path).exists()
        content = Path(path).read_text()
        assert "# Test" in content
