"""One-time OAuth setup for Google Analytics 4.

Re-uses the same OAuth client (`secrets/oauth-client.json`) you already created
for GSC, but requests the GA4 read-only scope and saves a separate token to
`secrets/ga4-token.json`.

Usage:
    python -m tools.ga4_oauth_setup
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]
ROOT = Path(__file__).resolve().parent.parent
SECRETS_DIR = ROOT / "secrets"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--client", default=str(SECRETS_DIR / "oauth-client.json"))
    ap.add_argument("--token-out", default=str(SECRETS_DIR / "ga4-token.json"))
    args = ap.parse_args()

    client_path = Path(args.client)
    token_path = Path(args.token_out)

    if not client_path.exists():
        print(f"❌ OAuth client file not found: {client_path}")
        print("Run `python -m tools.gsc_oauth_setup` first to create it, "
              "OR download a new OAuth Client ID JSON from GCP Console.")
        return 1

    SECRETS_DIR.mkdir(exist_ok=True)
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
    except ImportError:
        print("❌ google-auth-oauthlib not installed. Run: pip install -r requirements.txt")
        return 1

    print(f"📂 Using OAuth client: {client_path}")
    print("🌐 Opening browser to authenticate with Google for GA4 access…")
    print()

    flow = InstalledAppFlow.from_client_secrets_file(str(client_path), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")

    token_path.write_text(creds.to_json())
    print()
    print(f"✅ GA4 refresh token saved to: {token_path}")
    print()
    print("Add these to your .env (if not already there):")
    print(f"  GA4_OAUTH_TOKEN_JSON={token_path}")
    print(f"  GA4_PROPERTY_ID=<your 9-digit property ID from GA4 admin>")
    print()
    print("Then restart Streamlit. The GA4 dot in the sidebar will turn green.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
