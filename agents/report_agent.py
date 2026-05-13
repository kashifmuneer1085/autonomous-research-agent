"""
agents/report_agent.py
----------------------
Report Generation Agent — powered by Groq (FREE)

Responsibilities:
  1. Receive all analysis artefacts from AnalysisAgent.
  2. Generate a professional, structured Markdown research report.
  3. Include citations, source credibility scores, and a bibliography.

Uses Groq Llama-3.3-70b — completely free.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from groq import AsyncGroq

from core.config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


_REPORT_SYSTEM_PROMPT = """\
You are an expert technical writer specialising in research reports.
Write clear, professional, and well-structured reports in Markdown.
Be factual, cite evidence, and maintain a neutral, analytical tone.
Do not add any preamble before the report title.
"""

_REPORT_USER_PROMPT = """\
Generate a comprehensive research report in Markdown format for the following query:

**Research Question:** {query}

---

AVAILABLE RESEARCH DATA

Key Insights:
{key_insights}

Emerging Trends:
{trends}

Comparative Analysis Points:
{comparisons}

Statistics & Data:
{statistics}

Source Summaries (use these as your primary evidence base):
{source_summaries}

---

REPORT REQUIREMENTS

Structure the report with these exact sections:

# {title}

**Date:** {date}
**Sources Analysed:** {num_sources}

## Executive Summary
[2–3 paragraph overview of the most important findings]

## Introduction
[Context for the research question, why it matters, scope of this report]

## Key Findings
[Numbered list of the most impactful findings from the research]

## Detailed Analysis

### Key Insights
[Expand on each key insight with supporting evidence]

### Emerging Trends
[Discuss identified trends with their significance]

### Comparative Analysis
[Compare different approaches, tools, or studies where relevant]

### Statistics & Data
[Present key statistics in context, use tables where appropriate]

## Conclusion
[Synthesise findings, implications, and potential next steps]

## References
[Numbered bibliography of all sources used]

---

Generate the full report now. Be thorough and analytical. Aim for 800–1200 words of body content.
"""


class ReportGenerationAgent:
    """
    Agent 6 — Report Generation

    Synthesises all analysis outputs into a professional Markdown report.
    Powered by Groq (free tier).
    """

    def __init__(self) -> None:
        self.client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        self.model = settings.GROQ_MODEL_STRONG

    def _format_list(self, items: list[str]) -> str:
        if not items:
            return "_No data available._"
        return "\n".join(f"{i+1}. {item}" for i, item in enumerate(items))

    def _format_source_summaries(self, source_summaries: dict[str, str]) -> str:
        lines = []
        for i, (url, summary) in enumerate(source_summaries.items(), 1):
            lines.append(f"[Source {i}] ({url})\n{summary}\n")
        return "\n".join(lines) if lines else "_No source summaries available._"

    def _build_title(self, query: str) -> str:
        clean = re.sub(r"^(research:?\s*|what\s+is\s+)", "", query, flags=re.I).strip()
        words = clean.split()
        stopwords = {"a", "an", "the", "in", "on", "at", "for", "to", "of", "and", "or"}
        title_words = []
        for i, w in enumerate(words):
            if i == 0 or w.lower() not in stopwords:
                title_words.append(w.capitalize())
            else:
                title_words.append(w.lower())
        return " ".join(title_words)

    def _build_references_section(self, scored_sources: list[dict[str, Any]]) -> str:
        lines = []
        for i, src in enumerate(scored_sources, 1):
            url = src.get("url", "")
            title = src.get("title", url)
            score = src.get("credibility_score", 0.0)
            lines.append(f"{i}. [{title}]({url}) _(Credibility: {score:.1f})_")
        return "\n".join(lines)

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        Parameters
        ----------
        state : dict   Full ResearchState from the workflow.

        Returns
        -------
        dict with keys:
          - report_markdown : str
          - report_metadata : dict
        """
        query = state.get("refined_query", state.get("user_query", "Research Report"))
        key_insights = state.get("key_insights", [])
        trends = state.get("trends", [])
        comparisons = state.get("comparisons", [])
        statistics = state.get("statistics", [])
        source_summaries = state.get("source_summaries", {})
        scored_sources = state.get("scored_sources", [])

        title = self._build_title(query)
        date_str = datetime.now().strftime("%B %d, %Y")
        num_sources = len(source_summaries)

        logger.info("report_agent_start", title=title, sources=num_sources)

        prompt = _REPORT_USER_PROMPT.format(
            query=query,
            title=title,
            date=date_str,
            num_sources=num_sources,
            key_insights=self._format_list(key_insights),
            trends=self._format_list(trends),
            comparisons=self._format_list(comparisons),
            statistics=self._format_list(statistics),
            source_summaries=self._format_source_summaries(source_summaries),
        )

        response = await self.client.chat.completions.create(
            model=self.model,
            temperature=0.3,
            max_tokens=settings.GROQ_MAX_TOKENS,
            messages=[
                {"role": "system", "content": _REPORT_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )

        report_markdown = response.choices[0].message.content.strip()

        # Append references section if not already present
        if "## References" not in report_markdown and scored_sources:
            refs = self._build_references_section(scored_sources)
            report_markdown += f"\n\n## References\n\n{refs}"

        metadata = {
            "title": title,
            "query": query,
            "date": date_str,
            "num_sources": num_sources,
            "word_count": len(report_markdown.split()),
        }

        logger.info("report_agent_complete", title=title, word_count=metadata["word_count"])

        return {
            "report_markdown": report_markdown,
            "report_metadata": metadata,
        }
