"""Setup & Integrations view — PSI + GSC walkthroughs + status."""
from __future__ import annotations

import streamlit as st

from app.config import (
    ANTHROPIC_API_KEY,
    DISCORD_WEBHOOK_URL,
    GA4_OAUTH_TOKEN_JSON,
    GA4_PROPERTY_ID,
    GOOGLE_PAGESPEED_API_KEY,
    GSC_DEFAULT_SITE,
    GSC_OAUTH_TOKEN_JSON,
    GSC_SERVICE_ACCOUNT_JSON,
    NOTIFY_EMAIL_TO,
    SLACK_WEBHOOK_URL,
    SMTP_HOST,
    WEBPAGETEST_API_KEY,
)
from app.notifications import configured_channels, notify
from app.ui_helpers import ACCENT, BG_CARD, BORDER, TEXT_MUTED, TEXT_PRIMARY, logo_html

st.markdown(
    f"""
    <div style="background:linear-gradient(135deg,#0d1117 0%,#161B22 100%);
                border:1px solid {BORDER};border-radius:14px;
                padding:20px 24px;margin-bottom:24px;">
      <div style="display:flex;align-items:center;gap:14px;margin-bottom:6px;">
        {logo_html(height=36)}
        <div style="font-size:0.78rem;color:{ACCENT};letter-spacing:0.14em;
                    text-transform:uppercase;font-weight:600;">Configuration</div>
      </div>
      <h1 style="margin:0 0 8px;font-size:1.7rem;color:{TEXT_PRIMARY};">
        ⚙️ Setup & Integrations
      </h1>
      <div style="color:{TEXT_MUTED};font-size:0.92rem;line-height:1.55;">
        Wire up optional data sources. Each step is one-time. Restart Streamlit
        after adding a key (Ctrl+C then <code>./run.sh</code>).
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


def _status_chip(ok: bool, label: str) -> None:
    color = ACCENT if ok else "#F85149"
    text = "Connected" if ok else "Not connected"
    st.markdown(
        f'<span style="display:inline-block;padding:3px 10px;'
        f'background:{color}1F;color:{color};border-radius:99px;'
        f'font-size:0.78rem;font-weight:600;">● {text}</span> '
        f'<span style="color:{TEXT_MUTED};font-size:0.85rem;">{label}</span>',
        unsafe_allow_html=True,
    )


# ============================================================== Anthropic
with st.container(border=True):
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("### 🟣 Anthropic Claude API")
        st.caption("Powers the three agents. Required.")
    with col2:
        _status_chip(bool(ANTHROPIC_API_KEY), "")
    if not ANTHROPIC_API_KEY:
        st.markdown("""
1. Go to <https://console.anthropic.com/settings/keys>
2. **Create Key** → copy
3. Open `.env`: `cd ~/Downloads/SEO && open -e .env`
4. Set `ANTHROPIC_API_KEY=sk-ant-…`
5. Restart Streamlit.
""")
    else:
        st.caption("✅ Set up. Reads via `ANTHROPIC_API_KEY` env var.")

st.write("")

# ============================================================== PageSpeed
with st.container(border=True):
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("### 🟢 Google PageSpeed Insights")
        st.caption("Free API for Lighthouse scores + Core Web Vitals on every audit.")
    with col2:
        _status_chip(bool(GOOGLE_PAGESPEED_API_KEY), "")
    if not GOOGLE_PAGESPEED_API_KEY:
        st.markdown("""
**2-minute setup, no credit card needed:**

1. Go to <https://developers.google.com/speed/docs/insights/v5/get-started>
2. Click **Get a Key** (top-right). Sign in with the Google account you use for stoptions.ai.
3. Pick or create a project (any name — "Stoptions SEO" works).
4. Copy the key it generates (looks like `AIzaSy…`).
5. Open `.env`: `cd ~/Downloads/SEO && open -e .env`
6. Set:
   ```
   GOOGLE_PAGESPEED_API_KEY=AIzaSy…
   ```
7. Restart Streamlit (Ctrl+C then `./run.sh`).

**Quota without key:** ~25 requests/day per IP.
**Quota with key:** 25,000/day. Plenty for Daily Health Checks + ad-hoc audits.
""")
    else:
        masked = GOOGLE_PAGESPEED_API_KEY[:6] + "…" + GOOGLE_PAGESPEED_API_KEY[-4:]
        st.caption(f"✅ Connected. Key: `{masked}`")

st.write("")

# ============================================================== Google Search Console
gsc_connected = bool(GSC_OAUTH_TOKEN_JSON or GSC_SERVICE_ACCOUNT_JSON)
with st.container(border=True):
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("### 🔵 Google Search Console")
        st.caption("Pulls real Google queries, clicks, impressions, position data for stoptions.ai.")
    with col2:
        _status_chip(gsc_connected, "")

    if gsc_connected:
        mode = "OAuth (you)" if GSC_OAUTH_TOKEN_JSON else "Service account"
        path = GSC_OAUTH_TOKEN_JSON or GSC_SERVICE_ACCOUNT_JSON
        st.caption(f"✅ Connected via **{mode}**. Property: `{GSC_DEFAULT_SITE}`")
        st.caption(f"Credentials: `{path}`")
    else:
        st.markdown("**Two auth modes — pick one. OAuth is recommended for single-operator setups.**")

        oauth_tab, sa_tab = st.tabs(["🔐 OAuth (recommended)", "🔑 Service account"])

        with oauth_tab:
            st.markdown("""
**~5 min, doesn't fight GSC's user-add validation.** You authenticate once
with your Google account (which is already an Owner of the property); the
agents inherit your access.

#### Step 1 — Configure OAuth consent screen (once per GCP project)
1. <https://console.cloud.google.com/apis/credentials/consent?project=stoptions>
2. User type: **External** → Create.
3. App name: `Stoptions SEO Crew` · User support email: your email · Developer contact: your email → Save & continue.
4. **Scopes** → Save & continue (no extra scopes needed here).
5. **Test users** → **Add Users** → add your own email (e.g. `critter@rank1st.ca`) → Save.

#### Step 2 — Create the OAuth Client ID
1. <https://console.cloud.google.com/apis/credentials?project=stoptions>
2. **+ Create Credentials** → **OAuth client ID**.
3. Application type: **Desktop app**. Name: `Stoptions SEO Crew` → Create.
4. **DOWNLOAD JSON** on the success dialog.
5. Save it as `~/Downloads/SEO/secrets/oauth-client.json`:
   ```bash
   mkdir -p ~/Downloads/SEO/secrets
   mv ~/Downloads/client_secret_*.json ~/Downloads/SEO/secrets/oauth-client.json
   ```

#### Step 3 — Run the one-time auth flow
```bash
cd ~/Downloads/SEO
source .venv/bin/activate
python -m tools.gsc_oauth_setup
```

A browser tab opens to Google's consent screen. Sign in with the account
that owns the property → Allow. The script saves the refresh token to
`~/Downloads/SEO/secrets/gsc-token.json` and prints the env line to add.

#### Step 4 — Update `.env`
```
GSC_OAUTH_TOKEN_JSON=/Users/critter/Downloads/SEO/secrets/gsc-token.json
GSC_DEFAULT_SITE=sc-domain:stoptions.ai
```

(Use `sc-domain:` prefix for Domain properties; use `https://stoptions.ai/` for URL-prefix properties.)

#### Step 5 — Restart Streamlit
`Ctrl+C` then `./run.sh`. Dot turns green.
""")

        with sa_tab:
            st.markdown("""
For multi-tenant SaaS setups where the agents need to read GSC data without
a human in the loop. **Not recommended for single-operator setups** —
GSC's "Add user" flow often returns "email not found" for newly created
service accounts. If you must use this path:

#### Step 1 — Enable the API
<https://console.cloud.google.com/apis/library/searchconsole.googleapis.com>
→ Enable.

#### Step 2 — Create a service account
<https://console.cloud.google.com/iam-admin/serviceaccounts> → Create →
name `stoptions-seo-bot` → Done.

#### Step 3 — Generate JSON key
Click the SA → Keys → Add Key → Create new key → JSON. Save it:
```bash
mkdir -p ~/Downloads/SEO/secrets
mv ~/Downloads/*-*.json ~/Downloads/SEO/secrets/gsc-sa.json
```

#### Step 4 — Add the SA email as a user on the GSC property
GSC → Settings → Users and permissions → Add user → paste the SA email,
permission Restricted. **If this fails with "email not found", switch to
OAuth (left tab).**

#### Step 5 — Update `.env`
```
GSC_SERVICE_ACCOUNT_JSON=/Users/critter/Downloads/SEO/secrets/gsc-sa.json
GSC_DEFAULT_SITE=sc-domain:stoptions.ai
```

Restart Streamlit.
""")

st.write("")

# ============================================================== WebPageTest
with st.container(border=True):
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("### ⚪ WebPageTest  ·  *optional (Pro plan only)*")
        st.caption("Deeper perf data than PSI — filmstrip, network waterfall, repeat-view (caching). "
                   "The free Starter plan does NOT include API access — Pro starts at $180/year.")
    with col2:
        _status_chip(bool(WEBPAGETEST_API_KEY), "")
    if not WEBPAGETEST_API_KEY:
        st.markdown("""
**Status:** the agents already have everything they need via **PageSpeed Insights**
(Lighthouse + Core Web Vitals — free, no quota issues, already wired). WebPageTest
adds filmstrip + waterfall views that are useful for deep front-end debugging but
rarely needed for SEO work.

**If you ever do upgrade to WebPageTest Pro:**

1. <https://www.catchpoint.com/pricing#smb> → pick **Professional** ($180/year for 1000 tests/month, includes API).
2. After signing up, go to **Integrations → Legacy WPT API** in the Catchpoint portal.
3. Copy the API key (starts with `A.`).
4. Paste into `.env`:
   ```
   WEBPAGETEST_API_KEY=A.xxxxxxx
   ```
5. Restart Streamlit. The tool then becomes available to the agents.
""")
    else:
        masked = WEBPAGETEST_API_KEY[:6] + "…" + WEBPAGETEST_API_KEY[-4:]
        st.caption(f"✅ Connected via Pro plan. Key: `{masked}`")

st.write("")

# ============================================================== Google Analytics 4
ga4_connected = bool(GA4_OAUTH_TOKEN_JSON and GA4_PROPERTY_ID)
with st.container(border=True):
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("### 🟡 Google Analytics 4")
        st.caption("Real traffic, sources, landing pages + conversions. Closes the loop "
                   "SEO → traffic → trial signups.")
    with col2:
        _status_chip(ga4_connected, "")

    if ga4_connected:
        st.caption(f"✅ Connected. Property ID: `{GA4_PROPERTY_ID}`  ·  "
                   f"Token: `{GA4_OAUTH_TOKEN_JSON}`")
    else:
        st.markdown(f"""
**Status of your GA4:** Property ID `{GA4_PROPERTY_ID or '(not set)'}`,
OAuth token `{GA4_OAUTH_TOKEN_JSON or '(not generated)'}`.

#### Step 1 — Confirm Analytics Data API is enabled
<https://console.cloud.google.com/apis/library/analyticsdata.googleapis.com?project=stoptions>
→ should say "API Enabled".

#### Step 2 — Generate the GA4 OAuth token
Re-uses the existing `oauth-client.json` from your GSC setup, just adds the GA4
read-only scope:

```bash
cd ~/Downloads/SEO
source .venv/bin/activate
python -m tools.ga4_oauth_setup
```

Browser opens, sign in with `critter@rank1st.ca` (the account that owns the GA4
property), click Allow. Token saves to `secrets/ga4-token.json`.

#### Step 3 — Confirm `.env`
Already pre-populated:
```
GA4_PROPERTY_ID=538041737
GA4_OAUTH_TOKEN_JSON=/Users/critter/Downloads/SEO/secrets/ga4-token.json
```

#### Step 4 — Restart Streamlit
The GA4 dot turns green; the agents can call `ga4_top_pages`, `ga4_traffic_sources`,
`ga4_conversions`, `ga4_landing_pages`, `ga4_realtime_active_users`.

---

#### ⚠️ Install the GA4 tag on stoptions.ai
Property `Stoptions.ai → stoptions.ai`, Measurement ID **`G-VKH1WP56SH`**.
The API will work, but tools will return zeros until you install the tag.
Drop this in the `<head>` of every page:

```html
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-VKH1WP56SH"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', 'G-VKH1WP56SH');
</script>
```

For Webflow: Project Settings → Custom Code → Head Code → paste above.
For WordPress: Site Kit plugin or the GA4 plugin.
""")

st.write("")

# ============================================================== Notifications
chans = configured_channels()
with st.container(border=True):
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("### 🔔 Notifications")
        st.caption("Email + Slack + Discord. Fires when a scheduled run finds 🔴 critical issues.")
    with col2:
        _status_chip(bool(chans), "")
    if chans:
        st.caption(f"✅ Channels active: **{', '.join(chans)}**")
        if st.button("Send test notification"):
            res = notify(
                subject="Stoptions.ai SEO Crew — test notification",
                body_markdown="If you can read this, notifications are wired up correctly. 🎉",
                severity="info",
            )
            st.write(res)
    else:
        st.markdown("""
Set any combination of these in `.env`:

**Email (SMTP)** — any SMTP server (Gmail App Password / SendGrid / Mailgun / etc.)
```
NOTIFY_EMAIL_TO=you@yourdomain.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASS=app-password-here
SMTP_FROM=you@gmail.com
```

**Slack webhook** — Apps → Incoming Webhooks → Add to Workspace → pick channel.
```
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/XXX/YYY/ZZZ
```

**Discord webhook** — Server Settings → Integrations → Webhooks → New Webhook.
```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/XXX/YYY
```

Restart Streamlit after editing `.env`.
""")

st.write("")

# ============================================================== more
with st.container(border=True):
    st.markdown("### 🧩 More integrations (roadmap)")
    st.markdown("""
Each one is a wrapper away. Tell me which to wire up next:

| Integration | What it adds | Cost |
| --- | --- | --- |
| **GA4 (Google Analytics)** | Real traffic, conversion paths, trial-signup funnel | Free |
| **Bing Webmaster Tools** | Bing + Copilot queries — useful for AEO | Free |
| **DataForSEO** | Real Google SERPs (vs DuckDuckGo estimate), live SERP positions per market | ~$0.0006 / SERP |
| **Schema.org Validator API** | Validate generated JSON-LD before publish | Free |
| **WebPageTest** | Deeper perf data (filmstrip, network waterfall) | Free tier |
| **Ahrefs / SEMrush / Moz** | Real backlink + keyword databases | Paid |
""")
