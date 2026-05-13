---
title: Autonomous AI Research Agent
emoji: 🔬
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# 🔬 Autonomous AI Research Agent

[![Hugging Face Space](https://img.shields.io/badge/🤗_Spaces-Live_Demo-yellow?style=for-the-badge)](https://huggingface.co/spaces/kashif1085/autonomous-research-agent)
[![Streamlit App](https://img.shields.io/badge/Streamlit-Live_Demo-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://scoutai.streamlit.app)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

**🚀 Try it live:**
- HuggingFace Spaces (full pipeline): [kashif1085/autonomous-research-agent](https://huggingface.co/spaces/kashif1085/autonomous-research-agent)
- Streamlit Cloud (lite version): [scoutai.streamlit.app](https://scoutai.streamlit.app)

A production-ready, multi-agent AI system that automatically researches any topic — searching the web, scraping content, analysing findings, and delivering a structured report to Google Docs and Google Sheets.

Built with **LangGraph**, **Groq Llama 3.3 70B**, **FastAPI**, and **Streamlit**.

---

## Architecture Overview

```
User Query
    │
    ▼
┌─────────────────────────┐
│  Query Understanding    │  Refines query → 3 search variants
│  Agent (Groq Llama 3.3) │
└────────────┬────────────┘
             │
    ▼
┌─────────────────────────┐
│  Search Agent           │  DuckDuckGo Search → ranked URLs (free, no key)
│  (async, credibility    │  with credibility scoring
│   scored)               │
└────────────┬────────────┘
             │
    ▼
┌─────────────────────────┐
│  Scraper Agent          │  httpx → Playwright fallback
│  (parallel, retry)      │  BeautifulSoup content extraction
└────────────┬────────────┘
             │
    ▼
┌─────────────────────────┐
│  Content Processing     │  Chunking, deduplication (cosine sim),
│  Agent                  │  credibility annotation
└────────────┬────────────┘
             │
    ▼
┌─────────────────────────┐
│  Analysis Agent         │  Map: per-source summary (Groq Llama 3.3)
│  (Map-Reduce)           │  Reduce: synthesis → insights, trends,
│                         │  comparisons, statistics (Groq Llama 3.3)
└────────────┬────────────┘
             │
    ▼
┌─────────────────────────┐
│  Report Generation      │  Professional Markdown report with
│  Agent (Groq Llama 3.3) │  citations, TOC, bibliography
└────────────┬────────────┘
             │
    ▼
┌─────────────────────────┐
│  Storage Agent          │  → Local Markdown file
│                         │  → Google Docs (formatted)
│                         │  → Google Sheets (log row)
└─────────────────────────┘
```

---

## Project Structure

```
autonomous-research-agent/
├── agents/
│   ├── query_agent.py          # Query Understanding Agent
│   ├── search_agent.py         # Web Search Agent (DuckDuckGo — free, no key)
│   ├── scraper_agent.py        # Scraper Agent (httpx + Playwright)
│   ├── content_processor.py    # Content Processing Agent
│   ├── analysis_agent.py       # Analysis Agent (Map-Reduce LLM)
│   ├── report_agent.py         # Report Generation Agent
│   └── storage_agent.py        # Storage Agent (local + Google)
│
├── core/
│   ├── config.py               # Pydantic settings (env vars)
│   └── workflow.py             # LangGraph state machine
│
├── utils/
│   ├── logger.py               # Structured logging (structlog)
│   ├── scraper_utils.py        # Low-level scraping primitives
│   └── text_processing.py      # Chunking, dedup, credibility
│
├── api/
│   └── main.py                 # FastAPI REST backend
│
├── frontend/
│   └── streamlit_app.py        # Streamlit UI
│
├── tests/
│   └── test_agents.py          # Unit + integration tests
│
├── data/                       # Generated reports saved here
├── .env.example                # Environment variable template
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## Quick Start

### 1. Clone and Install

```bash
git clone https://github.com/kashifmuneer1085/autonomous-research-agent.git
cd autonomous-research-agent

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
playwright install chromium       # Install headless browser
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:
```
GROQ_API_KEY=gsk_...
```

Get a free Groq API key at [console.groq.com](https://console.groq.com).

### 3a. Run the Streamlit UI (simplest)

```bash
streamlit run frontend/streamlit_app.py
```

Open `http://localhost:8501` → type a query → click **Research**.

Use **Direct (in-process)** mode for the simplest experience — no separate backend needed.

### 3b. Run the FastAPI Backend (optional, for REST API access)

```bash
uvicorn api.main:app --reload --port 8000
```

Interactive API docs at `http://localhost:8000/docs`.

Then run Streamlit and switch the sidebar to **API (FastAPI backend)** mode.

### 3c. Run from Python directly

```python
import asyncio
from core.workflow import run_research_pipeline

result = asyncio.run(run_research_pipeline(
    "Latest AI tools for healthcare diagnosis"
))

print(result["report_markdown"])
print("Saved to:", result["local_file_path"])
```

---

## Execution Modes

The system supports two execution modes, both using the same underlying LangGraph pipeline:

| Mode | When to use | Architecture |
|---|---|---|
| **Direct (in-process)** | Local dev, demos, single user | Streamlit calls the pipeline as a Python function in the same process |
| **API (FastAPI backend)** | Production, multi-client, separate frontend/backend | Streamlit submits a job to FastAPI over HTTP and polls for results |

API mode demonstrates a service-oriented architecture with async job queues, Pydantic schemas, CORS middleware, and background tasks — useful for understanding how the system would scale beyond a single Streamlit instance.

---

## API Reference

### `POST /research`

Submit a research job (runs asynchronously).

```bash
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"query": "Latest AI tools for healthcare diagnosis"}'
```

Response:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Research job created. Poll GET /research/{job_id} for results."
}
```

### `GET /research/{job_id}`

Poll for results.

```bash
curl http://localhost:8000/research/550e8400-e29b-41d4-a716-446655440000
```

Response (when complete):
```json
{
  "job_id": "...",
  "status": "complete",
  "report_markdown": "# Latest AI Tools for Healthcare Diagnosis\n\n...",
  "report_metadata": { "title": "...", "word_count": 1050, "num_sources": 7 },
  "google_doc_url": "https://docs.google.com/document/d/.../edit",
  "google_sheet_url": "https://docs.google.com/spreadsheets/d/.../edit",
  "local_file_path": "data/20260512_120000_Latest_AI_Tools.md",
  "agent_logs": ["✓ Query Understanding", "✓ Search — 8 sources found", "..."]
}
```

---

## Google Integration Setup (Optional)

Google Docs and Sheets upload is **optional** — the pipeline falls back to local Markdown files when credentials are absent.

To enable cloud upload:

1. Go to [Google Cloud Console](https://console.cloud.google.com).
2. Create a new project (or select an existing one).
3. Enable these APIs:
   - **Google Docs API**
   - **Google Sheets API**
   - **Google Drive API**
4. Navigate to **APIs & Services → Credentials**.
5. Click **Create Credentials → OAuth 2.0 Client ID**.
6. Application type: **Desktop App** → Download JSON → rename to `credentials.json`.
7. Place `credentials.json` in the project root.
8. On first pipeline run, a browser window opens for Google consent.
   After authorising, `token.json` is cached — subsequent runs are fully automatic.

Set `GOOGLE_DRIVE_FOLDER_ID` in `.env` to save reports into a specific Drive folder
(find the ID in the folder URL: `https://drive.google.com/drive/folders/{FOLDER_ID}`).

---

## Docker Deployment

```bash
# Build and run both services
docker-compose up --build

# API  → http://localhost:8000/docs
# UI   → http://localhost:8501
```

Pass secrets via environment or a `.env` file:
```bash
GROQ_API_KEY=gsk_... docker-compose up
```

---

## Running Tests

```bash
# Unit tests only (no API key required)
pytest tests/ -v -m "not integration"

# All tests including LLM integration tests (requires GROQ_API_KEY)
pytest tests/ -v
```

---

## Configuration Reference

All settings live in `.env`. Full list in `.env.example`.

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | *(required)* | Free Groq API key (console.groq.com) |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model for all LLM tasks |
| `GROQ_MODEL_STRONG` | `llama-3.3-70b-versatile` | Groq model for report generation |
| Search | DuckDuckGo (built-in) | No key needed — works automatically |
| `MAX_SOURCES` | `8` | Max sources scraped per query |
| `NUM_SEARCH_QUERIES` | `3` | Search query variants to generate |
| `SCRAPER_CONCURRENCY` | `4` | Parallel scraping workers |
| `DEDUP_THRESHOLD` | `0.85` | Cosine similarity threshold for dedup |
| `DATA_DIR` | `data` | Local directory for saved reports |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

---

## Example Output

**Query:** `"Latest AI tools for healthcare diagnosis"`

**Report sections generated:**
- Executive Summary
- Introduction
- Key Findings (numbered, evidence-backed)
- Detailed Analysis
  - Key Insights
  - Emerging Trends
  - Comparative Analysis
  - Statistics & Data
- Conclusion
- References (with credibility scores)

---

## Advanced Features

### Source Credibility Scoring
Every URL is scored `[0.0 – 1.0]` based on domain tier:
- `1.0` — Nature, PubMed, IEEE, .gov, tier-1 news
- `0.7` — HTTPS + .edu / .org
- `0.5` — Generic HTTPS
- `0.2` — Blogs, Reddit, Quora
- `0.1` — HTTP (unencrypted)

### Semantic Deduplication
Chunks from different sources are compared using cosine similarity on a shared BoW vocabulary. Near-duplicate passages (≥ 0.85 similarity) are dropped before analysis, ensuring diverse evidence.

### Map-Reduce Analysis
- **Map**: Each source is summarised independently in parallel (fast, cheap).
- **Reduce**: All summaries are synthesised by Groq Llama 3.3 70B into insights, trends, comparisons, and statistics — enabling multi-document reasoning beyond a single context window.

### Two-Stage Scraping
1. **httpx** — lightweight, fast, handles static HTML.
2. **Playwright** — full headless Chromium for JS-rendered pages (SPAs, lazy-loaded content).

---

## License

MIT License. See `LICENSE` for details.
