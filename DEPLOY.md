# Deploy the Stoptions.ai SEO Crew

Three deployment paths, ordered by simplicity. Pick one.

---

## Option A — Self-managed VPS (DigitalOcean / Hetzner / Linode / OVH) — recommended

**You'll need:** a Linux box with Docker + Docker Compose, a domain name, and your Anthropic API key.

```bash
# 1. SSH in
ssh root@your-server

# 2. Install Docker
curl -fsSL https://get.docker.com | sh

# 3. Pull the project
cd /opt
git clone <your-repo-url> seo-crew && cd seo-crew

# 4. Configure
cp .env.example .env
nano .env    # paste ANTHROPIC_API_KEY (and optional GOOGLE_PAGESPEED_API_KEY)

# 5. Launch
docker compose up -d --build

# 6. Verify
curl -fsS http://localhost:8501/_stcore/health   # should return "ok"
docker logs -f stoptions-ai-seo-crew              # watch boot logs
```

### Reverse proxy with Caddy (auto-HTTPS)

```caddy
seo.yourdomain.com {
    reverse_proxy localhost:8501
    encode gzip zstd
}
```

`apt install caddy && systemctl enable --now caddy` then point your DNS A record at the box. Caddy provisions a Let's Encrypt cert automatically.

---

## Option B — Render.com (managed, no SSH)

1. Push the repo to GitHub.
2. **New → Web Service → Connect repo**.
3. Settings:
   - Environment: `Docker`
   - Branch: `main`
   - Region: closest to you
4. **Environment Variables:**
   - `ANTHROPIC_API_KEY` = `sk-ant-…`
   - `ANTHROPIC_MODEL` = `claude-sonnet-4-5`
   - `GOOGLE_PAGESPEED_API_KEY` (optional)
5. Deploy. Render gives you `https://yourapp.onrender.com`.

The Dockerfile already exposes 8501; Render auto-detects.

---

## Option C — Fly.io (global, edge-distributed)

```bash
# install flyctl, then:
fly launch --no-deploy --image python:3.11-slim
# answer "no" to creating a postgres / no to redis
fly secrets set ANTHROPIC_API_KEY=sk-ant-... ANTHROPIC_MODEL=claude-sonnet-4-5
fly deploy
```

Fly auto-detects the Dockerfile and exposes 8501.

---

## Putting it behind auth (so only you can use it)

Streamlit doesn't ship auth. Easiest options:

- **Caddy basic auth** in front (1-line config — see Caddy docs).
- **Cloudflare Access** (free tier, identity-aware proxy).
- **Tailscale + serve to your tailnet only** — zero ports exposed publicly.

---

## Persistent reports

The `./reports` directory is mounted as a Docker volume, so `analyst_report` Markdown files survive container restarts. Back them up with a nightly `rsync` cron or sync to S3:

```bash
0 3 * * * rsync -a /opt/seo-crew/reports/ /backup/seo/
```

---

## Updating the deployment

```bash
cd /opt/seo-crew
git pull
docker compose up -d --build
```

Zero downtime if you put it behind a reverse proxy with a brief health-check grace period.

---

## Cost ballpark

- **VPS:** $6–12 / month (Hetzner CX22 or DO Basic Droplet).
- **Anthropic API:** ~$0.05–$0.30 per full crew run (research → analyst → marketer) on Sonnet. Cheaper if you swap to Haiku for the researcher.
- **PageSpeed Insights:** free.
- **Google Search Console API:** free.
