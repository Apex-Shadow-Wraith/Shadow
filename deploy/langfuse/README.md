# Langfuse Self-Hosted — Project Shadow

Local observability stack for Shadow, deployed via Docker Compose.
Single-host, single-user, bound to `127.0.0.1` only.

**Bias / alignment disclosure:** Langfuse is observability-only — it does
not perform inference and has no model or alignment surface. MIT-licensed.
This deployment runs with `TELEMETRY_ENABLED=false` so the self-hosted
instance does not phone home to langfuse.com.

---

## Stack

| Service | Image | Host port | Container port | Purpose |
|---|---|---|---|---|
| langfuse-web | `langfuse/langfuse:3.172.0` | 127.0.0.1:3000 | 3000 | Web UI + API |
| langfuse-worker | `langfuse/langfuse-worker:3.172.0` | 127.0.0.1:3030 | 3030 | Async ingestion worker |
| postgres | `postgres:17.9` | 127.0.0.1:5433 | 5432 | Relational metadata |
| clickhouse | `clickhouse/clickhouse-server:25.8.22.28` | 127.0.0.1:8123, :9000 | 8123, 9000 | Trace storage |
| redis | `redis:7.4.8` | 127.0.0.1:6379 | 6379 | Queue + cache |
| minio | `minio/minio:RELEASE.2025-09-07T16-13-09Z` | 127.0.0.1:9090, :9091 | 9000, 9001 | S3-compatible blob store |

Postgres host port is `5433` (not 5432) because Citadel's system Postgres
holds 5432.

## Lifecycle

| Action | Command |
|---|---|
| Bring up | `docker compose up -d` |
| Bring down (preserve data) | `docker compose down` |
| Nuke and rebuild — DESTROYS DATA | `docker compose down -v && rm -rf data/` |
| Logs (live, web) | `docker compose logs -f langfuse-web` |
| Logs (live, worker) | `docker compose logs -f langfuse-worker` |
| Status | `docker compose ps` |
| Pull updates | `docker compose pull && docker compose up -d` |

## Access

- Web UI: <http://localhost:3000>
- MinIO console: <http://localhost:9091>
- API endpoint: <http://localhost:3000/api/public/>
- API keys: stored in `.env` as `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY`,
  populated after first-run admin setup.

## First-run setup

1. `docker compose up -d`
2. Wait ~30–60s for ClickHouse migrations to complete.
3. Open <http://localhost:3000>, create admin user.
4. Create organization (e.g., "Project Shadow") and project (e.g., "Citadel").
5. Settings → API Keys → Create new keys. Copy public + secret.
6. Paste into `.env`:
   ```
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   ```
7. Restart the Shadow processes that need observability — no `docker
   compose restart` required, keys are client-side.

## Disable observability for tests / CI

```bash
export LANGFUSE_DISABLED=1
```

`modules/shadow/observability` no-ops cleanly when this is set, when
keys are missing, or when the SDK isn't installed. Observability never
breaks production.

## Rotate API keys

1. Open <http://localhost:3000> → Settings → API Keys
2. Revoke old keys, generate new
3. Update `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` in `.env`
4. Restart Shadow processes — keys are read at client-init time

## Backup

Backups must run with the stack stopped (`docker compose down`) to avoid
torn writes.

**Bind-mounted volumes** — visible at filesystem level:
```bash
docker compose down
tar czf langfuse-backup-$(date +%F).tar.gz data/postgres data/redis data/minio
docker compose up -d
```

**Named volumes** — ClickHouse data + logs:
```bash
docker compose down
docker run --rm \
    -v langfuse_langfuse_clickhouse_data:/data \
    -v "$PWD":/backup busybox \
    tar czf /backup/clickhouse-data-$(date +%F).tar.gz -C /data .
docker run --rm \
    -v langfuse_langfuse_clickhouse_logs:/data \
    -v "$PWD":/backup busybox \
    tar czf /backup/clickhouse-logs-$(date +%F).tar.gz -C /data .
docker compose up -d
```

(Volume names are prefixed with the compose project name, which defaults
to the directory name `langfuse`. Adjust if your project name differs.)

ClickHouse uses named volumes because the official image runs as UID 101
without an auto-chown step; bind-mounting would require host-side `chown`
with root.

## Schema migrations

Langfuse runs Postgres + ClickHouse migrations on startup automatically.
After `docker compose pull`, expect 30–60s of migration time on the next
`up -d`.

## Image pin policy

All images pinned to specific versions (no `:latest`, no floating major
tags like `:3` or `:7`). Rationale: prior-session lesson — floating tags
silently drift on `docker compose pull` and break reproducibility. Update
pins explicitly when bumping versions; see `docker-compose.yml` header
for the bumped-on date.
