"""One-time OAuth setup for Google Search Console.

Reads a Google Cloud OAuth 2.0 Client ID JSON (Desktop App type), opens
your browser to authenticate as YOU, and saves a refresh token to disk.
Subsequent GSC API calls auto-refresh the token from this file.

Usage:
    python -m tools.gsc_oauth_setup

By default reads ~/Downloads/SEO/secrets/oauth-client.json and writes
~/Downloads/SEO/secrets/gsc-token.json. Override with --client / --token-out.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
ROOT = Path(__file__).resolve().parent.parent
SECRETS_DIR = ROOT / "secrets"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--client",
        default=str(SECRETS_DIR / "oauth-client.json"),
        help="Path to OAuth Client ID JSON downloaded from GCP Console.",
    )
    ap.add_argument(
        "--token-out",
        default=str(SECRETS_DIR / "gsc-token.json"),
        help="Where to save the resulting refresh-token JSON.",
    )
    args = ap.parse_args()

    client_path = Path(args.client)
    token_path = Path(args.token_out)

    if not client_path.exists():
        print(f"❌ OAuth client file not found: {client_path}\n")
        print("How to create one:")
        print("  1. Open https://console.cloud.google.com/apis/credentials")
        print("  2. Select the 'Stoptions' project.")
        print("  3. Click 'CREATE CREDENTIALS' → 'OAuth client ID'.")
        print("  4. If prompted, configure the OAuth consent screen first")
        print("     (External, add your email as a Test User).")
        print("  5. Application type: 'Desktop app'. Name: 'Stoptions SEO Crew'.")
        print("  6. Click CREATE → DOWNLOAD JSON.")
        print(f"  7. Save the downloaded file as: {client_path}")
        print()
        print("Then re-run this script.")
        return 1

    SECRETS_DIR.mkdir(exist_ok=True)

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
    except ImportError:
        print("❌ google-auth-oauthlib not installed. Run: pip install -r requirements.txt")
        return 1

    print(f"📂 Reading OAuth client from: {client_path}")
    print("🌐 Opening browser to authenticate with Google…")
    print("    (Sign in with the account that owns the Search Console property.)")
    print()

    flow = InstalledAppFlow.from_client_secrets_file(str(client_path), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")

    token_path.write_text(creds.to_json())

    print()
    print(f"✅ Refresh token saved to: {token_path}")
    print()
    print("Add this to your .env (if not already there):")
    print(f"  GSC_OAUTH_TOKEN_JSON={token_path}")
    print()
    print("Then restart Streamlit (Ctrl+C, ./run.sh) — the Search Console")
    print("dot in the sidebar will turn green.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
