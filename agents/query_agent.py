"""
agents/query_agent.py
---------------------
Query Understanding Agent — powered by Groq (FREE)

Responsibilities:
  1. Receive the raw user research question.
  2. Refine the query (correct spelling, disambiguate, add context).
  3. Generate multiple distinct search query variants to maximise coverage.

Uses Groq's Llama-3.3-70b — fast and completely free.
"""

from __future__ import annotations

import json
from typing import Any

from groq import AsyncGroq

from core.config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


_SYSTEM_PROMPT = """\
You are an expert research librarian and information architect.

Your task is to analyse a user's research question and produce:
1. A refined, precise version of the query suitable for academic/web research.
2. A list of {n} distinct search queries that together provide broad coverage of the topic.
   - Vary the angle: definitions, recent news, comparisons, statistics, expert opinions.
   - Include at least one query targeting recent developments (append "2024" or "2025").
   - Keep each query concise (≤ 10 words).

Respond ONLY with valid JSON in this exact schema:
{{
  "refined_query": "<refined single-sentence query>",
  "search_queries": ["<query 1>", "<query 2>", ...]
}}
No preamble, no markdown fences, just the JSON object.
"""


class QueryUnderstandingAgent:
    """
    Agent 1 — Query Understanding

    Expands a raw user query into a refined question and multiple search variants.
    Powered by Groq (free tier).
    """

    def __init__(self) -> None:
        self.client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        self.model = settings.GROQ_MODEL
        self.n_queries = settings.NUM_SEARCH_QUERIES

    async def run(self, user_query: str) -> dict[str, Any]:
        """
        Parameters
        ----------
        user_query : str
            Raw research question from the user.

        Returns
        -------
        dict with keys:
          - refined_query : str
          - search_queries : list[str]
        """
        logger.info("query_agent_start", raw_query=user_query)

        response = await self.client.chat.completions.create(
            model=self.model,
            temperature=0.3,
            max_tokens=512,
            messages=[
                {
                    "role": "system",
                    "content": _SYSTEM_PROMPT.format(n=self.n_queries),
                },
                {
                    "role": "user",
                    "content": f"Research question: {user_query}",
                },
            ],
        )

        raw_content = response.choices[0].message.content.strip()

        # Strip accidental markdown fences
        if raw_content.startswith("```"):
            raw_content = raw_content.split("```")[1]
            if raw_content.startswith("json"):
                raw_content = raw_content[4:]

        parsed: dict[str, Any] = json.loads(raw_content)

        refined_query: str = parsed.get("refined_query", user_query)
        search_queries: list[str] = parsed.get("search_queries", [user_query])

        if not search_queries:
            search_queries = [user_query]

        logger.info(
            "query_agent_complete",
            refined_query=refined_query,
            num_queries=len(search_queries),
        )

        return {
            "refined_query": refined_query,
            "search_queries": search_queries,
        }
