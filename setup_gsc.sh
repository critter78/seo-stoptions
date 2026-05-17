#!/usr/bin/env bash
# One-shot Google Search Console OAuth setup.
# Run this once from ~/Downloads/SEO after downloading the OAuth client JSON.
set -euo pipefail

cd "$(dirname "$0")"

echo "=========================================="
echo "  Stoptions SEO Crew — GSC OAuth setup"
echo "=========================================="
echo

mkdir -p secrets

# 1) Find the OAuth client JSON in ~/Downloads (most recent)
echo "🔎 Looking for OAuth client JSON in ~/Downloads…"
CLIENT_FILE=""
if [ -f secrets/oauth-client.json ]; then
  CLIENT_FILE="secrets/oauth-client.json"
  echo "✅ Already in place: $CLIENT_FILE"
else
  NEWEST=$(ls -t ~/Downloads/client_secret_*.json 2>/dev/null | head -n 1 || true)
  if [ -z "$NEWEST" ]; then
    echo "❌ Couldn't find a client_secret_*.json in ~/Downloads."
    echo
    echo "Go to https://console.cloud.google.com/auth/clients?project=stoptions"
    echo "→ click your 'Stoptions SEO Crew' client → Download JSON."
    echo "Then re-run this script."
    exit 1
  fi
  echo "📂 Found: $NEWEST"
  mv "$NEWEST" secrets/oauth-client.json
  CLIENT_FILE="secrets/oauth-client.json"
  echo "✅ Moved to: $CLIENT_FILE"
fi
echo

# 2) Activate venv
if [ ! -d ".venv" ]; then
  echo "❌ .venv not found. Run ./run.sh once first to install dependencies."
  exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# 3) Run the OAuth setup script (opens your browser)
echo "🌐 Opening Google's auth page in your browser…"
echo "   (Sign in with critter@rank1st.ca — the account that owns the GSC property.)"
echo
python -m tools.gsc_oauth_setup

echo
echo "🎉 All done. Now restart Streamlit:"
echo "   Ctrl+C in the Streamlit terminal, then ./run.sh"
echo "Search Console dot in the sidebar will turn green."
