# SearXNG Setup — Citadel (Ubuntu 24.04)

SearXNG is a self-hosted metasearch engine that queries Google, Bing,
DuckDuckGo, Brave, Reddit, GitHub, arXiv, and StackOverflow simultaneously and
returns combined results. Reaper uses it as the **primary** search backend in
the default `"ddg"` cascade (`modules/reaper/reaper.py`).

Runs in Docker on Citadel. Bound to `127.0.0.1` only — never exposed to the
LAN. The container holds no Shadow secrets; the only secret is its own
`server.secret_key`, sourced from an untracked `.env` file.

---

## Prerequisites

Docker is already installed on Citadel via the system package manager. Verify:

```bash
docker --version          # expect 28+
docker compose version    # expect v2.x (note: `docker compose`, not `docker-compose`)
```

---

## First-time bring-up

```bash
cd ~/dev/Shadow/services/searxng

# Generate the SearXNG server secret (one time only, host-side).
python3 -c "import secrets; print(f'SEARXNG_SECRET={secrets.token_hex(32)}')" > .env
chmod 600 .env

# Pull the image and start.
docker compose up -d
docker compose ps
```

`.env` is covered by the repo's root `.gitignore` (`.env` line). Do not commit
it. Rotating the secret is just regenerating the file and `docker compose
restart`.

---

## Verify

```bash
# HTML interface in a browser.
xdg-open http://localhost:8888

# JSON API (what Reaper hits).
curl -s 'http://localhost:8888/search?q=test&format=json' | jq '.results | length'
# expect: a positive integer (15-30 typical)

# Healthcheck endpoint (what the compose healthcheck hits).
curl -fsS http://localhost:8888/healthz

# From Python, with Reaper's actual code path.
python3 -c "
from modules.reaper.reaper import Reaper
r = Reaper()
print('searxng_available:', r._searxng_is_available())
results = r.search('rtx 5090 review', max_results=3)
print(f'{len(results)} results, first engine: {results[0][\"engine\"] if results else \"NONE\"}')
"
```

If `/healthz` is unavailable but `/search` works, the SearXNG image version
predates the healthz endpoint; the `docker compose ps` STATUS column will read
`(unhealthy)`. The data plane is still fine — bump the image and restart.

---

## CAPTCHA warmup (only if needed)

Some upstream engines (notably Google) occasionally rate-limit fresh IPs. If
JSON queries return empty `.results` while HTML works in the browser:

1. Open `http://localhost:8888` in a browser.
2. Run a manual search; if Google shows a CAPTCHA, solve it.
3. JSON API will then resolve normally.

Bing and DDG rarely require this.

---

## Operations

```bash
cd ~/dev/Shadow/services/searxng

# Stop
docker compose down

# Start
docker compose up -d

# Logs
docker compose logs -f

# Update image
docker compose pull && docker compose up -d

# Live container status
docker compose ps
```

SearXNG idle footprint: ~80 MB RAM, near-zero CPU. Safe to leave running 24/7.

---

## Run under systemd (optional)

The compose stack will auto-restart on container failure (`restart:
unless-stopped`), but Docker itself needs to come up at boot. On Citadel the
docker service is already enabled. To verify:

```bash
systemctl is-enabled docker
# expect: enabled
```

A future Phase B promotion may convert this to a per-user systemd unit at
`~/.config/systemd/user/shadow-searxng.service` parallel to
`daemons/cerberus_watchdog/`. Today, plain `docker compose up -d` is
sufficient.

---

## Stealth posture (verified June 2026)

The default SearXNG behavior — inherited via `use_default_settings: true` —
sets `User-Agent: Mozilla/5.0 ... Firefox/<150|151>` per outbound request via
`gen_useragent()` in `searx/search/processors/online.py`. The engines enabled
in `settings.yml` (Google, Bing, DDG, Brave, Reddit, GitHub, arXiv,
StackOverflow) do **not** invoke `searxng_useragent()` — that function (which
returns `SearXNG/<version>`) is only used by Photon, Marginalia, Wikidata,
Unsplash, Pixabay, and the autocomplete endpoint, none of which we enable.

`outgoing.useragent_suffix` defaults to empty string. Do not set a suffix —
the empty default is what keeps `SearXNG/<version>` from leaking even on
endpoints that *do* use `searxng_useragent()`.

`general.instance_name` is `"local"` (not "Shadow") and surfaces only on the
inbound HTML `/about` and `/stats` endpoints. The host bind is
`127.0.0.1:8888` so no upstream sees it.

---

## Troubleshooting

**"Port 8888 already in use"**
Another process is bound. `ss -ltnp | grep 8888` to identify, then either
stop it or change the compose port mapping (`"127.0.0.1:9999:8080"`) and
re-run.

**"JSON returns empty results but HTML works"**
Cold-start engines warming up, or upstream CAPTCHA — see the warmup section.

**"Reaper reports SearXNG ❌ Not running" with stack confirmed up**
Re-instantiate Reaper *after* the stack is healthy. The boot-race fix
(`_searxng_is_available()` TTL probe) auto-recovers within 60 seconds of the
next search call, so the symptom should be transient.

**"healthcheck status: unhealthy"**
`/healthz` may not exist on older SearXNG images. Bump the image:
`docker compose pull && docker compose up -d`.
