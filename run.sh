#!/usr/bin/env bash
# Local dev runner — creates venv on first call, installs deps, runs Streamlit.
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

pip install --upgrade pip >/dev/null
pip install -r requirements.txt

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "📝 Created .env from .env.example — fill in ANTHROPIC_API_KEY and re-run."
  exit 1
fi

streamlit run Home.py
