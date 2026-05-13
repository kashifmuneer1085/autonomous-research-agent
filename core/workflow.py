"""
core/workflow.py
----------------
LangGraph state machine that orchestrates all research agents end-to-end.

Graph topology:
  START
    → query_understanding
    → search
    → scrape
    → content_processing
    → analysis
    → report_generation
    → storage
  END

Each node is a thin adapter calling the corresponding agent module.
State is passed through a typed TypedDict so every node can read/write
the full pipeline context.
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any, Optional
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END

from agents.query_agent import QueryUnderstandingAgent
from agents.search_agent import SearchAgent
from agents.scraper_agent import ScraperAgent
from agents.analysis_agent import AnalysisAgent
from agents.report_agent import ReportGenerationAgent
from agents.storage_agent import StorageAgent
from utils.logger import get_logger

logger = get_logger(__name__)


# ── Shared Pipeline State ─────────────────────────────────────────────────────

class ResearchState(TypedDict, total=False):
    """
    Shared state threaded through every LangGraph node.

    All fields are Optional; agents populate them as the pipeline progresses.
    """
    # Input
    user_query: str                          # Raw user research question

    # Query Understanding Agent output
    refined_query: str                       # Cleaned, expanded query
    search_queries: list[str]                # Multiple search query variants

    # Search Agent output
    source_urls: list[str]                   # Candidate URLs from search
    scored_sources: list[dict[str, Any]]     # [{url, score, title}, ...]

    # Scraper Agent output
    scraped_content: dict[str, str]          # {url: raw_text}

    # Content Processing output
    processed_chunks: list[dict[str, Any]]   # [{url, chunk, credibility_score}]
    deduplicated_chunks: list[dict[str, Any]]

    # Analysis Agent output
    key_insights: list[str]
    trends: list[str]
    comparisons: list[str]
    statistics: list[str]
    source_summaries: dict[str, str]         # {url: per-source summary}

    # Report Generation Agent output
    report_markdown: str                     # Full report in Markdown
    report_metadata: dict[str, Any]          # Title, date, source count, etc.

    # Storage Agent output
    google_doc_url: Optional[str]
    google_sheet_url: Optional[str]
    local_file_path: Optional[str]

    # Execution metadata
    errors: list[str]                        # Non-fatal errors collected
    agent_logs: list[str]                    # Human-readable step log


# ── Node Implementations ──────────────────────────────────────────────────────

async def _node_query_understanding(state: ResearchState) -> ResearchState:
    logger.info("node_start", node="query_understanding")
    agent = QueryUnderstandingAgent()
    result = await agent.run(state["user_query"])
    return {
        **state,
        "refined_query": result["refined_query"],
        "search_queries": result["search_queries"],
        "agent_logs": state.get("agent_logs", []) + ["✓ Query Understanding"],
    }


async def _node_search(state: ResearchState) -> ResearchState:
    logger.info("node_start", node="search")
    agent = SearchAgent()
    result = await agent.run(state["search_queries"])
    return {
        **state,
        "source_urls": result["urls"],
        "scored_sources": result["scored_sources"],
        "agent_logs": state.get("agent_logs", []) + [
            f"✓ Search — {len(result['urls'])} sources found"
        ],
    }


async def _node_scrape(state: ResearchState) -> ResearchState:
    logger.info("node_start", node="scrape")
    agent = ScraperAgent()
    result = await agent.run(state["source_urls"])
    return {
        **state,
        "scraped_content": result["scraped_content"],
        "agent_logs": state.get("agent_logs", []) + [
            f"✓ Scraping — {result['successful']} pages scraped"
        ],
    }


async def _node_content_processing(state: ResearchState) -> ResearchState:
    logger.info("node_start", node="content_processing")
    from agents.content_processor import ContentProcessingAgent
    agent = ContentProcessingAgent()
    result = await agent.run(state["scraped_content"], state.get("scored_sources", []))
    return {
        **state,
        "processed_chunks": result["processed_chunks"],
        "deduplicated_chunks": result["deduplicated_chunks"],
        "agent_logs": state.get("agent_logs", []) + [
            f"✓ Content Processing — {len(result['deduplicated_chunks'])} unique chunks"
        ],
    }


async def _node_analysis(state: ResearchState) -> ResearchState:
    logger.info("node_start", node="analysis")
    agent = AnalysisAgent()
    result = await agent.run(
        query=state["refined_query"],
        chunks=state["deduplicated_chunks"],
        scored_sources=state.get("scored_sources", []),
    )
    return {
        **state,
        "key_insights": result["key_insights"],
        "trends": result["trends"],
        "comparisons": result["comparisons"],
        "statistics": result["statistics"],
        "source_summaries": result["source_summaries"],
        "agent_logs": state.get("agent_logs", []) + ["✓ Analysis"],
    }


async def _node_report_generation(state: ResearchState) -> ResearchState:
    logger.info("node_start", node="report_generation")
    agent = ReportGenerationAgent()
    result = await agent.run(state)
    return {
        **state,
        "report_markdown": result["report_markdown"],
        "report_metadata": result["report_metadata"],
        "agent_logs": state.get("agent_logs", []) + ["✓ Report Generated"],
    }


async def _node_storage(state: ResearchState) -> ResearchState:
    logger.info("node_start", node="storage")
    agent = StorageAgent()
    result = await agent.run(state)
    return {
        **state,
        "google_doc_url": result.get("google_doc_url"),
        "google_sheet_url": result.get("google_sheet_url"),
        "local_file_path": result.get("local_file_path"),
        "agent_logs": state.get("agent_logs", []) + ["✓ Storage"],
    }


# ── Graph Assembly ────────────────────────────────────────────────────────────

def build_research_graph() -> StateGraph:
    """
    Assemble and compile the LangGraph research workflow.

    Returns a compiled graph ready for `.ainvoke()`.
    """
    graph = StateGraph(ResearchState)

    # Register nodes
    graph.add_node("query_understanding", _node_query_understanding)
    graph.add_node("search", _node_search)
    graph.add_node("scrape", _node_scrape)
    graph.add_node("content_processing", _node_content_processing)
    graph.add_node("analysis", _node_analysis)
    graph.add_node("report_generation", _node_report_generation)
    graph.add_node("storage", _node_storage)

    # Define edges (linear pipeline)
    graph.add_edge(START, "query_understanding")
    graph.add_edge("query_understanding", "search")
    graph.add_edge("search", "scrape")
    graph.add_edge("scrape", "content_processing")
    graph.add_edge("content_processing", "analysis")
    graph.add_edge("analysis", "report_generation")
    graph.add_edge("report_generation", "storage")
    graph.add_edge("storage", END)

    return graph.compile()


# ── Public Entry Point ────────────────────────────────────────────────────────

async def run_research_pipeline(user_query: str) -> ResearchState:
    """
    Run the full research pipeline for *user_query*.

    Returns the final ResearchState containing the report, URLs, logs, etc.
    """
    logger.info("pipeline_start", query=user_query)

    graph = build_research_graph()
    initial_state: ResearchState = {
        "user_query": user_query,
        "errors": [],
        "agent_logs": [],
    }

    final_state: ResearchState = await graph.ainvoke(initial_state)

    logger.info(
        "pipeline_complete",
        query=user_query,
        sources=len(final_state.get("scored_sources", [])),
        doc_url=final_state.get("google_doc_url"),
    )
    return final_state
