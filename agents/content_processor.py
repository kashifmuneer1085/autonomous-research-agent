"""
agents/content_processor.py
----------------------------
Content Processing Agent

Responsibilities:
  1. Receive raw scraped text per URL.
  2. Split into overlapping chunks.
  3. Annotate each chunk with its source URL and credibility score.
  4. Deduplicate chunks across all sources.
  5. Limit chunks per document to avoid token bloat.

Output feeds directly into AnalysisAgent.
"""

from __future__ import annotations

from typing import Any

from utils.text_processing import (
    chunk_text,
    deduplicate_texts,
    truncate_to_tokens,
)
from core.config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class ContentProcessingAgent:
    """
    Agent 4 — Content Processing

    Converts scraped text → annotated, deduplicated chunks ready for LLM analysis.
    """

    def __init__(self) -> None:
        self.chunk_size = settings.CHUNK_SIZE
        self.chunk_overlap = settings.CHUNK_OVERLAP
        self.max_chunks_per_doc = settings.MAX_CHUNKS_PER_DOC

    async def run(
        self,
        scraped_content: dict[str, str],
        scored_sources: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Parameters
        ----------
        scraped_content : dict[str, str]
            {url: text} from ScraperAgent.
        scored_sources : list[dict]
            [{url, credibility_score, ...}] from SearchAgent.

        Returns
        -------
        dict with keys:
          - processed_chunks : list[dict]   (before deduplication)
          - deduplicated_chunks : list[dict]
        """
        logger.info("content_processor_start", num_docs=len(scraped_content))

        # Build URL → credibility score lookup
        cred_map: dict[str, float] = {
            s["url"]: s.get("credibility_score", 0.5)
            for s in scored_sources
        }

        processed_chunks: list[dict[str, Any]] = []

        for url, text in scraped_content.items():
            if not text:
                continue

            # Truncate to stay within reasonable LLM token budget
            text = truncate_to_tokens(text, max_chars=settings.MAX_CONTENT_LENGTH)

            # Split into overlapping chunks
            chunks = chunk_text(text, self.chunk_size, self.chunk_overlap)

            # Limit chunks per document
            chunks = chunks[: self.max_chunks_per_doc]

            credibility = cred_map.get(url, 0.5)

            for i, chunk in enumerate(chunks):
                processed_chunks.append({
                    "url": url,
                    "chunk_index": i,
                    "chunk": chunk,
                    "credibility_score": credibility,
                })

        logger.info("content_processor_chunks", total=len(processed_chunks))

        # Semantic deduplication across all chunks
        chunk_texts = [c["chunk"] for c in processed_chunks]
        unique_texts = set(deduplicate_texts(chunk_texts, threshold=settings.DEDUP_THRESHOLD))

        deduplicated_chunks = [
            c for c in processed_chunks if c["chunk"] in unique_texts
        ]

        logger.info(
            "content_processor_dedup",
            before=len(processed_chunks),
            after=len(deduplicated_chunks),
        )

        return {
            "processed_chunks": processed_chunks,
            "deduplicated_chunks": deduplicated_chunks,
        }
