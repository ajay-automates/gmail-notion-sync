#!/usr/bin/env python3
"""
Run this script LOCALLY (not on Railway) to regenerate your Gmail OAuth token.

Usage:
  pip install google-auth-oauthlib google-auth
  python3 generate_token.py

It will open a browser (or print a URL if running headless), complete the
OAuth flow, and print the token JSON to paste into Railway's GMAIL_TOKEN
environment variable.
"""

import json
import sys
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


def main():
    import os
    if not os.path.exists('credentials.json'):
        print("❌ credentials.json not found in current directory.")
        print("   Download it from Google Cloud Console:")
        print("   APIs & Services → Credentials → OAuth 2.0 Client → Download JSON")
        sys.exit(1)

    print("🔑 Starting Gmail OAuth flow...")
    print("   A browser window will open. Sign in and grant access.\n")

    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)

    try:
        # Try browser-based flow first
        creds = flow.run_local_server(port=0)
    except Exception:
        # Fallback: console flow (paste the URL manually, copy the code back)
        creds = flow.run_console()

    token_json = creds.to_json()

    # Write locally as backup
    with open('token.json', 'w') as f:
        f.write(token_json)
    print("✅ token.json saved locally.\n")

    print("=" * 60)
    print("📋 Copy the value below into Railway → Variables → GMAIL_TOKEN")
    print("=" * 60)
    # Print as a single-line JSON so it's easy to paste
    print(json.dumps(json.loads(token_json)))
    print("=" * 60)
    print("\n✅ Done! Redeploy your Railway service after updating the variable.")


if __name__ == "__main__":
    main()
