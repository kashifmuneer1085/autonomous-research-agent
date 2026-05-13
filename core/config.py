"""
core/config.py
--------------
Central configuration for the Autonomous AI Research Agent.
All settings are loaded from environment variables with sensible defaults.

FREE STACK:
  LLM    → Groq (free tier, no credit card) — console.groq.com
  Search → DuckDuckGo (no API key needed, completely free)
"""

from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Create a .env file in the project root to override defaults.
    """

    # ── LLM — Groq (FREE) ─────────────────────────────────────────────────────
    # Sign up at https://console.groq.com → API Keys → Create API Key
    GROQ_API_KEY: str = Field(..., description="Groq API key (free at console.groq.com)")

    # Fast model  — used for query expansion and per-source summaries
    GROQ_MODEL: str = Field("llama-3.3-70b-versatile", description="Primary Groq model")
    # Strong model — used for analysis synthesis and report generation
    GROQ_MODEL_STRONG: str = Field("llama-3.3-70b-versatile", description="Strong Groq model")

    GROQ_TEMPERATURE: float = Field(0.2, description="LLM temperature")
    GROQ_MAX_TOKENS: int = Field(4096, description="Max tokens per LLM call")

    # ── Search — DuckDuckGo (FREE, no key needed) ────────────────────────────
    # No API key required — uses duckduckgo-search Python library
    MAX_SEARCH_RESULTS: int = Field(10, description="URLs to collect per query")
    NUM_SEARCH_QUERIES: int = Field(3, description="Search queries to generate")

    # ── Scraping ──────────────────────────────────────────────────────────────
    SCRAPER_TIMEOUT_S: int = Field(20, description="Per-page scraping timeout (s)")
    MAX_CONTENT_LENGTH: int = Field(15_000, description="Max chars per scraped page")
    SCRAPER_CONCURRENCY: int = Field(4, description="Parallel scraping workers")

    # ── Content Processing ────────────────────────────────────────────────────
    CHUNK_SIZE: int = Field(1500, description="Chunk size for text splitting (chars)")
    CHUNK_OVERLAP: int = Field(200, description="Overlap between chunks (chars)")
    MAX_CHUNKS_PER_DOC: int = Field(10, description="Max chunks analysed per document")
    DEDUP_THRESHOLD: float = Field(0.85, description="Cosine similarity dedup threshold")

    # ── Agent ─────────────────────────────────────────────────────────────────
    MAX_RETRIES: int = Field(3, description="Retry attempts for failed agent steps")
    MAX_SOURCES: int = Field(8, description="Max sources used in final report")

    # ── Google Integration ────────────────────────────────────────────────────
    GOOGLE_CREDENTIALS_FILE: str = Field(
        "credentials.json", description="Path to Google OAuth credentials JSON"
    )
    GOOGLE_TOKEN_FILE: str = Field(
        "token.json", description="Path to cached Google OAuth token"
    )
    GOOGLE_DRIVE_FOLDER_ID: str = Field(
        "", description="Drive folder ID to save reports into (root if empty)"
    )

    # ── Storage ───────────────────────────────────────────────────────────────
    DATA_DIR: str = Field("data", description="Local directory for saving outputs")
    LOG_LEVEL: str = Field("INFO", description="Logging level: DEBUG|INFO|WARNING|ERROR")

    # ── API Server ────────────────────────────────────────────────────────────
    API_HOST: str = Field("0.0.0.0", description="FastAPI host")
    API_PORT: int = Field(8000, description="FastAPI port")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()


# Convenience alias used throughout the codebase
settings = get_settings()
