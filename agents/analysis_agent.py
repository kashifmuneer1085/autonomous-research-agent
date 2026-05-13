"""
agents/analysis_agent.py
------------------------
Analysis Agent — powered by Groq (FREE)

Responsibilities:
  1. Group chunks by source URL.
  2. Summarise each source individually (map step).
  3. Perform multi-document synthesis across all summaries (reduce step).
  4. Extract: key insights, trends, comparisons, statistics.

Uses Groq Llama-3.3-70b for both map and reduce steps — completely free.
Implements a map-reduce pattern to stay within context limits.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from groq import AsyncGroq

from core.config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


# ── Prompts ───────────────────────────────────────────────────────────────────

_SOURCE_SUMMARY_PROMPT = """\
You are a senior research analyst. Read the following content from a single web source
and write a concise, factual summary (150–250 words) focused on information relevant
to the research question: "{query}"

Highlight:
- Core claims or findings
- Any statistics or data points
- Expert names or organisations mentioned
- Date/recency signals

Content:
{content}
"""

_SYNTHESIS_PROMPT = """\
You are a senior research analyst performing multi-document synthesis.

Research question: "{query}"

You have summaries from {n} sources below.

Produce a rigorous analysis structured as valid JSON with these keys:
{{
  "key_insights": [
    "<insight 1 — factual, specific>",
    "<insight 2>",
    "<insight 3>"
  ],
  "trends": [
    "<emerging pattern or development 1>",
    "<emerging pattern 2>"
  ],
  "comparisons": [
    "<comparison between tools/approaches/studies>"
  ],
  "statistics": [
    "<specific number / percentage / metric with context>"
  ]
}}

Rules:
- Each list should have 3–6 items.
- Be specific: avoid vague generalities.
- If a category has no data, use an empty list [].
- Output ONLY the JSON object, no markdown fences, no preamble.

Source summaries:
{summaries}
"""


# ── Agent ─────────────────────────────────────────────────────────────────────

class AnalysisAgent:
    """
    Agent 5 — Analysis (Map-Reduce)

    Map:    Summarise each source individually using Groq Llama (free).
    Reduce: Synthesise all summaries into structured insights using Groq Llama (free).
    """

    def __init__(self) -> None:
        self.client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        self.model = settings.GROQ_MODEL
        self.model_strong = settings.GROQ_MODEL_STRONG

    # ── Map step ──────────────────────────────────────────────────────────────

    async def _summarise_source(
        self, url: str, content: str, query: str
    ) -> tuple[str, str]:
        """Return (url, summary) for a single source."""
        prompt = _SOURCE_SUMMARY_PROMPT.format(query=query, content=content[:6000])
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                temperature=0.1,
                max_tokens=512,
                messages=[
                    {"role": "system", "content": "You are a concise, factual research analyst."},
                    {"role": "user", "content": prompt},
                ],
            )
            summary = response.choices[0].message.content.strip()
            logger.debug("source_summarised", url=url, words=len(summary.split()))
            return url, summary
        except Exception as exc:
            logger.warning("source_summary_failed", url=url, error=str(exc))
            return url, ""

    async def _map_step(
        self,
        chunks: list[dict[str, Any]],
        query: str,
    ) -> dict[str, str]:
        """
        Concatenate chunks per URL then summarise each source sequentially
        (Groq free tier has rate limits so we avoid hammering in parallel).
        Returns {url: summary}.
        """
        url_content: dict[str, str] = {}
        for c in chunks:
            url = c["url"]
            url_content[url] = url_content.get(url, "") + "\n\n" + c["chunk"]

        source_summaries: dict[str, str] = {}
        for url, content in url_content.items():
            _, summary = await self._summarise_source(url, content, query)
            if summary:
                source_summaries[url] = summary
            # Small delay to respect Groq rate limits (free tier: ~30 req/min)
            await asyncio.sleep(0.5)

        return source_summaries

    # ── Reduce step ───────────────────────────────────────────────────────────

    async def _reduce_step(
        self,
        source_summaries: dict[str, str],
        query: str,
    ) -> dict[str, Any]:
        """Synthesise all source summaries into structured insights."""
        formatted_summaries = "\n\n---\n\n".join(
            f"Source [{i+1}] ({url}):\n{summary}"
            for i, (url, summary) in enumerate(source_summaries.items())
        )

        prompt = _SYNTHESIS_PROMPT.format(
            query=query,
            n=len(source_summaries),
            summaries=formatted_summaries,
        )

        response = await self.client.chat.completions.create(
            model=self.model_strong,
            temperature=0.2,
            max_tokens=settings.GROQ_MAX_TOKENS,
            messages=[
                {"role": "system", "content": "You are a senior analyst. Output only valid JSON."},
                {"role": "user", "content": prompt},
            ],
        )

        raw = response.choices[0].message.content.strip()

        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        parsed = json.loads(raw)
        return {
            "key_insights": parsed.get("key_insights", []),
            "trends": parsed.get("trends", []),
            "comparisons": parsed.get("comparisons", []),
            "statistics": parsed.get("statistics", []),
        }

    # ── Public Entry Point ────────────────────────────────────────────────────

    async def run(
        self,
        query: str,
        chunks: list[dict[str, Any]],
        scored_sources: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Parameters
        ----------
        query : str   Refined research question.
        chunks : list[dict]   Deduplicated content chunks from ContentProcessingAgent.
        scored_sources : list[dict]   Source metadata from SearchAgent.

        Returns
        -------
        dict with keys: key_insights, trends, comparisons, statistics, source_summaries
        """
        logger.info("analysis_agent_start", num_chunks=len(chunks), query=query)

        if not chunks:
            logger.warning("analysis_agent_no_chunks")
            return {
                "key_insights": [],
                "trends": [],
                "comparisons": [],
                "statistics": [],
                "source_summaries": {},
            }

        # Map: summarise each source
        source_summaries = await self._map_step(chunks, query)

        if not source_summaries:
            logger.warning("analysis_agent_no_summaries")
            return {
                "key_insights": [],
                "trends": [],
                "comparisons": [],
                "statistics": [],
                "source_summaries": {},
            }

        # Reduce: synthesise insights
        synthesis = await self._reduce_step(source_summaries, query)

        logger.info(
            "analysis_agent_complete",
            insights=len(synthesis["key_insights"]),
            trends=len(synthesis["trends"]),
        )

        return {
            **synthesis,
            "source_summaries": source_summaries,
        }
