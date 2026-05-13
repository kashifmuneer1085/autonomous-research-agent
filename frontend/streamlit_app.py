"""
frontend/streamlit_app.py
--------------------------
Streamlit UI for the Autonomous AI Research Agent.

Run with:
  streamlit run frontend/streamlit_app.py

The app can either:
  A) Call the FastAPI backend (API_URL set in sidebar)
  B) Run the LangGraph pipeline directly in-process (no API required)
"""

from __future__ import annotations

import asyncio
import sys
import os
from pathlib import Path

import streamlit as st

# Ensure the project root is on sys.path when running directly
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── Page Config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AI Research Agent",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    /* Main header */
    .main-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 2rem;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 2rem;
    }
    .main-header h1 { color: #e2e8f0; margin: 0; font-size: 2.2rem; }
    .main-header p  { color: #94a3b8; margin-top: 0.5rem; font-size: 1rem; }

    /* Metric cards */
    .metric-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 1.2rem;
        text-align: center;
    }
    .metric-value { font-size: 2rem; font-weight: 700; color: #60a5fa; }
    .metric-label { font-size: 0.85rem; color: #94a3b8; margin-top: 0.3rem; }

    /* Agent progress steps */
    .step-done    { color: #22c55e; font-weight: 600; }
    .step-running { color: #f59e0b; font-weight: 600; }
    .step-pending { color: #64748b; }

    /* Report container */
    .report-box {
        background: #0f172a;
        border: 1px solid #1e40af;
        border-radius: 12px;
        padding: 2rem;
        max-height: 600px;
        overflow-y: auto;
    }

    /* Links */
    a { color: #60a5fa !important; }
</style>
""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("⚙️ Configuration")

    run_mode = st.radio(
        "Execution Mode",
        ["Direct (in-process)", "API (FastAPI backend)"],
        help="Direct mode runs the pipeline inside Streamlit — recommended. "
             "API mode requires the FastAPI server to be running separately on port 8000.",
    )

    if run_mode == "API (FastAPI backend)":
        st.warning(
            "⚠️ API mode requires the FastAPI backend to be running.\n\n"
            "Start it with:\n```\nuvicorn api.main:app --port 8000\n```\n\n"
            "**Recommended: use Direct mode instead.**",
            icon="⚠️",
        )
        api_url = st.text_input(
            "FastAPI Base URL", value="http://localhost:8000"
        )
    else:
        st.success("✅ Direct mode — no extra server needed.", icon="✅")
        api_url = None

    st.divider()
    st.markdown("**Pipeline Steps**")
    steps = [
        "🧠 Query Understanding",
        "🔍 Web Search",
        "🌐 Scraping",
        "📄 Content Processing",
        "🔬 Analysis",
        "📝 Report Generation",
        "💾 Storage",
    ]
    step_placeholders = [st.empty() for _ in steps]
    for i, step in enumerate(steps):
        step_placeholders[i].markdown(f"<span class='step-pending'>○ {step}</span>", unsafe_allow_html=True)

    st.divider()
    st.caption("Autonomous AI Research Agent v1.0")


# ── Helper: update step UI ────────────────────────────────────────────────────

def _mark_step(idx: int, done: bool = True) -> None:
    icon = "✓" if done else "⟳"
    cls  = "step-done" if done else "step-running"
    step_placeholders[idx].markdown(
        f"<span class='{cls}'>{icon} {steps[idx]}</span>",
        unsafe_allow_html=True
    )


# ── Main Header ───────────────────────────────────────────────────────────────

st.markdown("""
<div class="main-header">
    <h1>🔬 Autonomous AI Research Agent</h1>
    <p>Powered by LangGraph · Groq Llama-3.3-70b · DuckDuckGo Search (100% Free)</p>
</div>
""", unsafe_allow_html=True)


# ── Query Input ───────────────────────────────────────────────────────────────

col1, col2 = st.columns([4, 1])
with col1:
    query = st.text_input(
        "Research Query",
        placeholder="e.g. Latest AI tools for healthcare diagnosis",
        label_visibility="collapsed",
    )
with col2:
    start_btn = st.button("🚀 Research", use_container_width=True, type="primary")

st.caption("Enter any research topic. The agent will search, scrape, analyse, and report automatically.")


# ── Example Queries ───────────────────────────────────────────────────────────

with st.expander("💡 Example queries"):
    examples = [
        "Latest AI tools for healthcare diagnosis",
        "Quantum computing breakthroughs 2024",
        "Impact of generative AI on software development",
        "State of large language models 2025",
        "Climate tech startups raising funding 2024",
    ]
    for ex in examples:
        if st.button(ex, key=ex):
            query = ex
            start_btn = True


# ── Research Execution ────────────────────────────────────────────────────────

if start_btn and query.strip():
    st.divider()

    # Progress UI
    progress_bar = st.progress(0, text="Initialising pipeline…")
    status_box = st.empty()
    results_placeholder = st.empty()

    step_names_to_idx = {
        "query_understanding": 0,
        "search": 1,
        "scrape": 2,
        "content_processing": 3,
        "analysis": 4,
        "report_generation": 5,
        "storage": 6,
    }

    if run_mode == "Direct (in-process)":
        # ── Direct mode: run pipeline inline ──────────────────────────────────
        from core.workflow import run_research_pipeline

        status_box.info("🚀 Starting research pipeline…")

        # Patch step markers via simple progress tracking
        # (LangGraph doesn't expose per-node callbacks in compile mode easily,
        #  so we update after completion for now)
        for i in range(len(steps)):
            _mark_step(i, done=False)
        _mark_step(0, done=False)

        with st.spinner("Running autonomous research pipeline…"):
            try:
                result = asyncio.run(run_research_pipeline(query))
            except Exception as exc:
                st.error(f"Pipeline error: {exc}")
                st.stop()

        # Mark all done
        for i in range(len(steps)):
            _mark_step(i, done=True)

        progress_bar.progress(100, text="✅ Complete!")

    else:
        # ── API mode: poll the FastAPI backend ────────────────────────────────
        import httpx, time

        status_box.info(f"Submitting job to {api_url}…")

        try:
            resp = httpx.post(
                f"{api_url}/research",
                json={"query": query},
                timeout=30,
            )
            resp.raise_for_status()
            job_id = resp.json()["job_id"]
            st.info(f"Job ID: `{job_id}`")
        except Exception as exc:
            st.error(f"Failed to submit job: {exc}")
            st.stop()

        # Poll
        completed_steps = set()
        while True:
            time.sleep(3)
            try:
                poll = httpx.get(f"{api_url}/research/{job_id}", timeout=15)
                poll.raise_for_status()
                data = poll.json()
            except Exception as exc:
                st.warning(f"Polling error: {exc}")
                continue

            status = data["status"]
            logs = data.get("agent_logs") or []
            done_count = len(logs)
            progress_bar.progress(
                min(done_count * 14, 95),
                text=f"Running… ({done_count}/{len(steps)} steps done)",
            )

            for i in range(done_count):
                if i not in completed_steps:
                    _mark_step(i, done=True)
                    completed_steps.add(i)

            if status == "complete":
                for i in range(len(steps)):
                    _mark_step(i, done=True)
                progress_bar.progress(100, text="✅ Complete!")
                result = data
                break
            elif status == "failed":
                st.error(f"Job failed: {data.get('errors')}")
                st.stop()

    # ── Display Results ────────────────────────────────────────────────────────

    st.success("✅ Research complete!")
    st.divider()

    # Metrics row
    metadata = result.get("report_metadata") or {}
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{metadata.get('num_sources', 0)}</div>
            <div class="metric-label">Sources Analysed</div>
        </div>""", unsafe_allow_html=True)
    with m2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{metadata.get('word_count', 0):,}</div>
            <div class="metric-label">Report Words</div>
        </div>""", unsafe_allow_html=True)
    with m3:
        doc_status = "✓" if result.get("google_doc_url") else "–"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{doc_status}</div>
            <div class="metric-label">Google Doc Saved</div>
        </div>""", unsafe_allow_html=True)
    with m4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{"✓" if result.get("local_file_path") else "–"}</div>
            <div class="metric-label">Local File Saved</div>
        </div>""", unsafe_allow_html=True)

    st.divider()

    # Tabs: Report | Agent Logs | Storage Links
    tab_report, tab_logs, tab_links = st.tabs(["📄 Report", "🤖 Agent Logs", "🔗 Output Links"])

    with tab_report:
        report_md = result.get("report_markdown", "_No report generated._")
        st.markdown(report_md)
        st.download_button(
            "⬇️ Download Report (.md)",
            data=report_md,
            file_name=f"{metadata.get('title', 'report')}.md",
            mime="text/markdown",
        )

    with tab_logs:
        logs = result.get("agent_logs", [])
        if logs:
            for log in logs:
                st.markdown(f"- {log}")
        else:
            st.caption("No agent logs available.")

    with tab_links:
        if result.get("google_doc_url"):
            st.markdown(f"**📄 Google Doc:** [{result['google_doc_url']}]({result['google_doc_url']})")
        if result.get("google_sheet_url"):
            st.markdown(f"**📊 Google Sheet:** [{result['google_sheet_url']}]({result['google_sheet_url']})")
        if result.get("local_file_path"):
            st.markdown(f"**💾 Local File:** `{result['local_file_path']}`")
        if not any([result.get("google_doc_url"), result.get("google_sheet_url")]):
            st.caption("Google integration not configured. See README for setup instructions.")

elif start_btn and not query.strip():
    st.warning("Please enter a research query.")
