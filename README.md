# Stoptions.ai SEO Crew

A 3-agent AI SEO team for **[Stoptions.ai](https://stoptions.ai/)** — built with **LangGraph + Claude
+ Streamlit**. The crew autonomously researches, audits, and writes
execution-ready SEO recommendations and marketing artefacts to grow trial
signups and PRO+ subscriptions.

## Team Mamba

Three elite SEO operators. Mamba mentality — obsessive prep, no hedging, refuse to lose.

| | Name | Pronouns | Role | Tagline |
| --- | --- | --- | --- | --- |
| 🔎 | **Kira "Recon" Nakamura** | she/her | Senior SEO Researcher | _"If you've got something to prove, the work has to be visible."_ |
| 🧠 | **Cassius "Cash" Reed** | he/him | Principal Technical SEO Analyst | _"Three issues, ranked. Fix the top one this week or nothing else matters."_ |
| 📣 | **Maya Vega** | she/her | SEO Marketer | _"Work harder than you have to. Then keep working."_ |

**The audience:** international retail option traders. Priority markets in order: **USA, Europe, Canada, Australia, Asia**. The crew handles geo nuance (UK ISA / AU SMSF / US PDT / CA TFSA terminology, market hours, regional SERP differences) automatically.

Internal LangGraph node names: `researcher`, `analyst`, `seo_marketer`. Persona registry lives in [`agents/personas.py`](agents/personas.py).

All three share a common toolkit (DuckDuckGo, BeautifulSoup, on-page audit,
JSON-LD extractor, robots/sitemap, PageSpeed, Search Console, free backlink
signals via Wayback + Common Crawl, SERP analyser, rank estimator).

## Run locally

```bash
# 1. clone / cd into this folder
cd /Users/critter/Downloads/SEO

# 2. create venv + install deps + launch
./run.sh
```

`run.sh` will copy `.env.example` → `.env` on first run. Add your
`ANTHROPIC_API_KEY` and re-run.

The Streamlit app opens at <http://localhost:8501>.

## Run in Docker

```bash
docker compose up --build
```

Reports are persisted to `./reports` on the host.

## Environment variables

| Variable | Required | Notes |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | ✅ | Claude API key |
| `ANTHROPIC_MODEL` | – | Defaults to `claude-sonnet-4-5` |
| `GOOGLE_PAGESPEED_API_KEY` | – | Free, lifts PSI quota |
| `GSC_SERVICE_ACCOUNT_JSON` | – | Path to a service-account file with GSC read access |
| `GSC_DEFAULT_SITE` | – | Defaults to `https://stoptions.ai/` |
| `DEFAULT_DOMAIN` / `DEFAULT_TARGET_URL` | – | Default targets surfaced in the UI |

## Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -q
```

`tests/test_imports.py` is offline. `tests/test_tools.py` hits the real web
for cheap free-tool smoke checks.

## Deploying to a server

Any container host works (Render, Fly.io, Railway, a $6 VPS, etc.):

1. Push this repo to a private Git host.
2. On the server: `git pull && docker compose up -d --build`.
3. Point your reverse-proxy (Caddy / Nginx / Traefik) at `:8501`.
4. Add your env vars (Render/Fly: dashboard secrets; VPS: write `.env`).
5. Reports persist in the mounted `./reports` volume.

A minimal Caddyfile:

```
seo.yourdomain.com {
    reverse_proxy localhost:8501
}
```

## Project layout

```
SEO/
├── streamlit_app.py        # UI entry point — main chat
├── pages/
│   ├── 1_📂_Past_Reports.py    # browse / search saved reports
│   ├── 2_📊_Rank_Tracker.py    # SQLite rank history + chart
│   ├── 3_⏰_Scheduled_Runs.py  # cron-style scheduler
│   └── 4_👥_The_Crew.py        # Team Mamba roster + ethos
├── scheduled_run.py        # CLI entry for cron / launchd / GitHub Actions
├── app/
│   ├── config.py           # env loader + status summary
│   └── db.py               # SQLite (rank_history, schedules)
├── agents/
│   ├── personas.py         # Team Mamba registry (Kira, Cash, Maya)
│   ├── llm.py              # Claude factory
│   ├── researcher.py       # Kira (ReAct)
│   ├── analyst.py          # Cash (ReAct)
│   ├── marketer.py         # Maya (ReAct)
│   └── graph.py            # LangGraph supervisor
├── tools/                  # All SEO tools (LangChain @tool functions)
├── prompts/                # Per-agent system prompts (Markdown)
├── data/                   # SQLite DB (gitignored)
├── reports/                # Generated MD reports (gitignored)
├── tests/                  # Smoke tests
├── Dockerfile
└── docker-compose.yml
```

## Multipage dashboard

The Streamlit app has 5 pages:

1. **Main** — chat with the crew, run any SEO task, watch progress live (Kira → Cash → Maya).
2. **📂 Past Reports** — every saved report, filter by date, full-text search across them.
3. **📊 Rank Tracker** — SQLite-backed rank history, charts per keyword, manual rank-check form.
4. **⏰ Scheduled Runs** — define recurring crew tasks; the page generates the cron / launchd / GitHub Actions snippet for you. Execution is done by `scheduled_run.py`.
5. **👥 The Crew** — meet Team Mamba: roster, voice samples, team ethos.

## Adding a tool

1. Create `tools/your_tool.py` with a `@tool`-decorated function.
2. Import + add it to `ALL_TOOLS` in `tools/__init__.py`.
3. The agents pick it up automatically.

## Adding/upgrading a paid backlink/keyword API

Drop the wrapper in `tools/backlinks.py` (or a new `tools/ahrefs.py`), gate it
on the env var, and add it to `ALL_TOOLS`.
