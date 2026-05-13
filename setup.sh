#!/bin/bash
# =============================================================
#  Autonomous AI Research Agent — Conda Environment Setup
#  Usage: bash setup.sh
#
#  Everything (pip packages + playwright browser) is installed
#  INSIDE the conda environment — nothing touches the system.
# =============================================================

set -e  # Exit immediately on any error

# ── Colors ────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

ENV_NAME="research-agent"
PYTHON_VERSION="3.11"

echo ""
echo -e "${CYAN}=================================================${NC}"
echo -e "${CYAN}   Autonomous AI Research Agent — Setup Script  ${NC}"
echo -e "${CYAN}=================================================${NC}"
echo ""

# ── Step 1: Check conda is installed ─────────────────────────
echo -e "${YELLOW}[1/7] Checking conda installation...${NC}"
if ! command -v conda &> /dev/null; then
    echo -e "${RED}❌ conda not found. Please install Miniconda or Anaconda first:${NC}"
    echo "    https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi
echo -e "${GREEN}✅ conda found: $(conda --version)${NC}"
echo ""

# ── Step 2: Initialise conda shell integration ────────────────
# This makes `conda activate` work inside bash scripts
echo -e "${YELLOW}[2/7] Initialising conda shell integration...${NC}"
# Find conda.sh — works for both Miniconda and Anaconda
CONDA_BASE=$(conda info --base)
# shellcheck disable=SC1091
source "${CONDA_BASE}/etc/profile.d/conda.sh"
echo -e "${GREEN}✅ conda shell ready (base: ${CONDA_BASE})${NC}"
echo ""

# ── Step 3: Create conda environment ─────────────────────────
echo -e "${YELLOW}[3/7] Creating conda environment '${ENV_NAME}' (Python ${PYTHON_VERSION})...${NC}"
if conda env list | grep -q "^${ENV_NAME} \|^${ENV_NAME}$"; then
    echo -e "${YELLOW}⚠️  Environment '${ENV_NAME}' already exists. Skipping creation.${NC}"
    echo -e "    To recreate it from scratch run:"
    echo -e "    ${CYAN}conda remove -n ${ENV_NAME} --all -y && bash setup.sh${NC}"
else
    conda create -n "$ENV_NAME" python="$PYTHON_VERSION" pip -y
    echo -e "${GREEN}✅ Environment created.${NC}"
fi
echo ""

# ── Step 4: Activate the environment ─────────────────────────
echo -e "${YELLOW}[4/7] Activating environment '${ENV_NAME}'...${NC}"
conda activate "$ENV_NAME"

# Confirm we are inside the right env
ACTIVE_ENV=$(conda info --envs | grep "^\*" | awk '{print $1}')
ENV_PYTHON=$(which python)
echo -e "${GREEN}✅ Active env : ${ACTIVE_ENV}${NC}"
echo -e "${GREEN}✅ Python path: ${ENV_PYTHON}${NC}"
echo ""

# ── Step 5: Install all Python dependencies inside the env ───
echo -e "${YELLOW}[5/7] Installing Python dependencies from requirements.txt...${NC}"
echo -e "    (All packages go into: $(conda info --base)/envs/${ENV_NAME}/)"
echo ""

# Upgrade pip first — inside the active env
python -m pip install --upgrade pip --quiet

# Install all project dependencies
pip install -r requirements.txt

echo ""
echo -e "${GREEN}✅ All Python packages installed inside '${ENV_NAME}'.${NC}"
echo ""

# ── Step 6: Install Playwright browser inside the env ────────
echo -e "${YELLOW}[6/7] Installing Playwright Chromium browser (inside conda env)...${NC}"
# playwright is now installed in the env; run it directly
python -m playwright install chromium --with-deps
echo -e "${GREEN}✅ Playwright Chromium installed inside '${ENV_NAME}'.${NC}"
echo ""

# ── Step 7: Set up .env and data directory ───────────────────
echo -e "${YELLOW}[7/7] Setting up project files...${NC}"

if [ -f ".env" ]; then
    echo -e "${YELLOW}⚠️  .env already exists — skipping copy to preserve your keys.${NC}"
else
    cp .env.example .env
    echo -e "${GREEN}✅ .env created from .env.example${NC}"
fi

mkdir -p data
echo -e "${GREEN}✅ data/ directory ready.${NC}"
echo ""

# ── Summary ───────────────────────────────────────────────────
echo -e "${CYAN}=================================================${NC}"
echo -e "${GREEN}🎉 Setup complete! Everything is inside '${ENV_NAME}'.${NC}"
echo -e "${CYAN}=================================================${NC}"
echo ""
echo -e "${RED}⚠️  ONE ACTION REQUIRED — add your free Groq API key:${NC}"
echo ""
echo -e "    Open ${CYAN}.env${NC} and set:"
echo -e "    ${CYAN}GROQ_API_KEY=gsk_...${NC}"
echo ""
echo -e "    Get a free key (no credit card) at:"
echo -e "    ${CYAN}https://console.groq.com${NC}  →  API Keys  →  Create API Key"
echo ""
echo -e "    DuckDuckGo search requires no key — it works automatically."
echo ""
echo -e "─────────────────────────────────────────────────────"
echo -e "  HOW TO RUN (always activate the env first)"
echo -e "─────────────────────────────────────────────────────"
echo ""
echo -e "  ${CYAN}conda activate ${ENV_NAME}${NC}"
echo ""
echo -e "  Streamlit UI:"
echo -e "  ${CYAN}streamlit run frontend/streamlit_app.py${NC}"
echo -e "  → opens at http://localhost:8501"
echo ""
echo -e "  FastAPI backend:"
echo -e "  ${CYAN}uvicorn api.main:app --reload --port 8000${NC}"
echo -e "  → API docs at http://localhost:8000/docs"
echo ""
echo -e "  Run tests:"
echo -e "  ${CYAN}pytest tests/ -v${NC}"
echo ""
echo -e "  Deactivate when done:"
echo -e "  ${CYAN}conda deactivate${NC}"
echo ""
