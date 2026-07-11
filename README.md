# FM Assistant — Client Deployment & Operations Guide

The **FM Assistant** is a self-contained chat application that lets facility-management users talk to their **Bruce BEM** system in plain language — "search for the primary chilled-water pump," "create a work request for asset 49641" — and have it call the Bruce BEM API for them. It ships as one bundle you run on your own Linux VM.

Under the hood it's a **Rain-patched [LibreChat](https://librechat.ai)** (the chat UI + AI runtime) wired to a **Bruce BEM MCP tool server** (the bridge that turns a chat request into a Bruce API call). The whole system is **6 Docker containers** brought up with a single `docker compose` command — you operate them as one unit, not individually.

It runs in **two modes**, and you choose one at install time:
- **Standalone** — users open FM Assistant directly in a browser and log in to the chat app itself. Bruce calls run under one configured Bruce service account. *(This is `STAGING_MODE`.)*
- **Embedded (iframe)** — FM Assistant is embedded inside Bruce BEM; each user's Bruce calls run as **themselves**, using the token Bruce BEM forwards. Requires a Bruce-side integration.

This guide covers both, end-to-end: prerequisites, install, the `.env` reference, and day-2 operations (troubleshooting, logging, backup, monitoring).

---

## 1. Glossary — only what you need to operate

| Term | What it means for you |
|---|---|
| **LibreChat** | The chat interface your users talk to — a web UI in the browser. It's the "chat UI + AI runtime." |
| **MCP server** | The bridge between LibreChat and the **Bruce BEM API**. When a user asks "search for assets" or "create a work request," LibreChat asks the MCP server, which calls Bruce BEM. |
| **Bruce BEM** | Your facilities/asset-management system. FM Assistant reads from and writes to it through the MCP server — it's the system of record, FM Assistant is the conversational front door. |
| **The Bruce agent** | A pre-built assistant — **"Bruce Facility Management Assistant"** — seeded automatically on first boot and pre-selected in the model menu. It's what carries the Bruce tools; users just pick it and chat. |
| **Standalone mode** (`STAGING_MODE=true`) | FM Assistant runs on its own; users log into the chat app directly, and Bruce calls run under one configured Bruce service account. |
| **Embedded mode** (iframe) | FM Assistant runs *inside* Bruce BEM; each user's Bruce calls run as themselves, using the token Bruce forwards. |

Everything else in the stack — **MongoDB, Meilisearch, pgvector, rag_api** — is internal plumbing. You don't operate them individually; treat the **6 containers as one bundled system** brought up with a single command.

---

## 2. Architecture

**The bundle: 6 Docker containers, one network, started together.**

| Container | What it does | Exposed? |
|---|---|---|
| **api** | LibreChat — the chat UI your users see | ✅ published on the host (`API_PORT`, default 3080) |
| **archibus_fastmcp** | MCP server — the bridge to Bruce BEM | internal only (port 8000) |
| **mongodb** | Chat history, users, agent config | internal only |
| **meilisearch** | Message search index (rebuildable) | internal only |
| **vectordb** | Document embeddings for RAG (rebuildable) | internal only |
| **rag_api** | Document Q&A engine | internal only |

**How they talk.** All 6 share one Docker network. LibreChat reaches the MCP server at the internal hostname `http://archibus_fastmcp:8000/mcp` — never an external URL. **Only the `api` (UI) container is exposed** to the host; you put your reverse proxy + TLS in front of that.

**The two auth models** — this is the one architectural choice you make:

| | **Standalone** (`STAGING_MODE=true`) | **Embedded** (iframe, default) |
|---|---|---|
| How users reach it | Browse to FM Assistant directly, register/log in | Open it *inside* Bruce BEM |
| Who Bruce calls run as | One **shared service account** (`USERNAME`/`PASSWORD` in `.env`) | **Each user, as themselves** (Rain token Bruce forwards) |
| Bruce-side setup needed | None | Yes — Bruce embeds the iframe + injects tokens |
| Best when | A standalone FM Assistant, no Bruce login required | Users already work inside Bruce BEM |

Both models use the **same Bruce OAuth credentials** (`OAUTH_CLIENT_ID` / `CLIENT_SECRET` / `AUDIENCE` / `OAUTH_URL`) — the difference is only *how the per-user token is obtained*. §4 shows the install for each; §5 lists which `.env` vars each needs.

---

## 3. Prerequisites

| What | Recommended |
|---|---|
| **OS** | Dedicated Linux VM — Ubuntu 22.04 or 24.04 LTS |
| **CPU / RAM** | 4 vCPU / 8 GB comfortable; 2 / 4 minimum. *(The `api` image builds frontend assets on first boot — 8 GB avoids the memory-pressure build failure noted in §6.)* |
| **Disk** | 50 GB (volumes ≤ ~5 GB; headroom for logs + growth) |
| **Docker** | Docker Engine 24+ (includes Compose v2). Install: `https://get.docker.com/` |
| **Outbound network** | HTTPS to the **Bruce BEM API** + auth URLs, your **AI provider** (OpenRouter + OpenAI), and Docker/registry.librechat.ai |
| **Domain** | A public domain (e.g. `fm-assistant.your-domain.com`) with a valid **TLS cert** |
| **Reverse proxy** | nginx / Caddy / Traefik terminating HTTPS → `localhost:${API_PORT}` (3080) |
| **AI provider keys** | **OpenRouter key** (`OPENROUTER_KEY`) — powers the chat + the Bruce agent; one key reaches all frontier models (default: Claude Sonnet 4.6). **OpenAI key** (`OPENAI_API_KEY`) — powers document-embeddings only (`rag_api`); required even on OpenRouter, or `rag_api` crash-loops. |
| **Bruce BEM credentials** | From the **Bruce team (Rein Suurväli)** — OAuth M2M client (`OAUTH_CLIENT_ID` / `CLIENT_SECRET`), `USER_API_CLIENT_ID`, the OAuth + BEM + user-auth URLs, and — for standalone mode — a Bruce `USERNAME` / `PASSWORD`. Full list in §5. |

**Per environment.** If you run more than one environment (e.g. Qatar **dev** and **pre**), each needs its own Bruce credential set and URLs — same variable names, different values.

---

## 4. Install

**Common steps (both modes):**

```bash
# 1. Get the code
git clone https://github.com/veloxforce/archibus-deploy.git
cd archibus-deploy

# 2. Create your env file and fill it in (see §5 for every variable)
cp .env.example .env
#    - set a stable COMPOSE_PROJECT_NAME (e.g. fm-assistant-prod) so volumes survive renames
#    - set DOMAIN_CLIENT / DOMAIN_SERVER to your public host
#    - fill the Bruce credentials from Rein, plus OPENROUTER_KEY + OPENAI_API_KEY
```

Then pick **one** mode below. When it's up, **wait for all 6 containers healthy**:

```bash
docker compose ps        # all 6 should read (healthy) within ~90s
```

> **First-boot note:** on a low-memory VM the *first* build can silently ship a broken `api` image (the frontend build fails under memory pressure). If the UI returns 502, just rebuild — `docker compose ... up -d --build` again reaches 6/6. See §6.

### 4a — Standalone mode (`STAGING_MODE=true`)

In `.env`: set `STAGING_MODE=true` and fill `USERNAME` / `PASSWORD` (the shared Bruce account). Bring the stack up with the staging overlay:

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.override.yml \
  -f docker-compose.staging.yml \
  up -d --build
```

Then:
1. Point your reverse proxy at `localhost:${API_PORT}` (3080).
2. Open `https://your-domain/` → **register the first user** at `/register` (`ALLOW_REGISTRATION=true` ships on).
3. In the chat, the **"Bruce Facility Management Assistant"** agent is already selected. Ask *"search for assets"* — a real Bruce `search_assets` call should return live assets.

### 4b — Embedded mode (iframe, `STAGING_MODE=false`)

Leave `STAGING_MODE=false` (default). Bring the stack up normally:

```bash
docker compose up -d --build
```

Then:
1. Point your reverse proxy at `localhost:${API_PORT}` (3080).
2. **Bruce-side cutover** (done by the Bruce team): update the FM Assistant iframe `src` in Bruce BEM to `https://your-domain/?userToken=…&refreshToken=…`. The token query params are unchanged — only the host changes.
3. Smoke test: open Bruce BEM → the FM Assistant iframe → ask *"search for assets"* → confirm the tool call succeeds under your own Bruce identity.

---

## 5. `.env` — what you must fill

`.env.example` ships with working defaults for everything internal (ports, DB names, embeddings, registration). **You only need to set these:**

```bash
# ── Secrets — generate your own (LibreChat has a generator; never reuse examples) ──
CREDS_KEY=                 # 32-byte hex
CREDS_IV=                  # 16-byte hex
JWT_SECRET=                # random 32+ char
JWT_REFRESH_SECRET=        # random 32+ char
MEILI_MASTER_KEY=          # random 32+ char
POSTGRES_PASSWORD=         # any strong value

# ── Your host ─────────────────────────────────────────────────────
DOMAIN_CLIENT=https://your-domain    # change from the localhost default
DOMAIN_SERVER=https://your-domain

# ── AI provider keys ──────────────────────────────────────────────
OPENROUTER_KEY=            # chat + Bruce agent (all frontier models)
OPENAI_API_KEY=            # embeddings only — required, or rag_api crash-loops

# ── Bruce BEM auth [both modes] — from Rein ───────────────────────
OAUTH_CLIENT_ID=           # Bruce OAuth M2M client id
CLIENT_SECRET=             # Bruce OAuth M2M secret
OAUTH_URL=                 # Bruce token URL (…/oauth/token)
AUDIENCE=                  # Bruce OAuth audience
USER_API_CLIENT_ID=        # Bruce user-API client id
BEM_API_URL=               # full URL, incl. https:// and trailing /api/
USER_AUTH_URL=             # full URL, incl. https:// and trailing /api/

# ── Standalone mode only ──────────────────────────────────────────
STAGING_MODE=true          # set true for standalone (default is false = embedded)
USERNAME=                  # shared Bruce account — all users' calls run as this
PASSWORD=                  # that account's password
```

> Everything else in `.env.example` (`API_PORT`, `POSTGRES_DB/USER`, `ALLOW_REGISTRATION`, `EMBEDDINGS_*`) already works as shipped — change it only if you have a reason.

---

## 6. Troubleshooting

First move for any container issue: `docker compose ps` (find who's unhealthy), then `docker compose logs <service> --tail 100`.

| Symptom | Cause | Fix |
|---|---|---|
| UI returns **502 / won't load** right after first boot | `api` built a broken frontend under memory pressure (silent, first build only) | Rebuild: `docker compose … up -d --build` — reaches 6/6. Give the VM ≥ 8 GB (§3). |
| `rag_api` **crash-loops** on boot | `OPENAI_API_KEY` empty — embeddings can't start | Set `OPENAI_API_KEY`; keep `EMBEDDINGS_PROVIDER=openai` |
| Chat + AI reply work, but **Bruce tool calls fail** ("search assets" / "create work request") | Bruce credentials or URLs wrong | `docker compose logs archibus_fastmcp --tail 50`; check `OAUTH_CLIENT_ID` / `CLIENT_SECRET` / `USER_API_CLIENT_ID` and `BEM_API_URL` / `USER_AUTH_URL` (full URL, trailing `/api/`) |
| **Standalone**: tool calls fail with an auth error | Shared Bruce account creds wrong, or `STAGING_MODE` not `true` | Confirm `STAGING_MODE=true` + `USERNAME`/`PASSWORD`; `docker compose … restart archibus_fastmcp` |

---

## 7. Logging

View logs through Compose:

```bash
docker compose logs <service> --tail 100     # last 100 lines
docker compose logs <service> -f             # follow live
docker compose logs --since 1h               # last hour, all services
```

Services: `api`, `archibus_fastmcp`, `mongodb`, `meilisearch`, `vectordb`, `rag_api`.

Containers log via Docker's default **json-file** driver. **No rotation is configured out of the box** — on a long-running host, add `max-size` / `max-file` to the compose logging options (or your host's Docker daemon) if you want size caps.

**Credential discipline:** the MCP server has a `RAIN_DEBUG` flag, **off by default**. Setting `RAIN_DEBUG=1` emits credential-adjacent diagnostics (client-id and token prefixes) to the logs — leave it unset in production; enable it only briefly to debug an auth failure, then unset and `restart archibus_fastmcp`.

---

## 8. Backup

Backup is your responsibility (integrate with your ASC-HS tooling). What to protect:

| Volume | Contents | If lost |
|---|---|---|
| **`mongo_data`** | Chat history, users, agent config | **Irreplaceable — back this up** |
| `meili_data` | Message search index | Rebuilds from MongoDB automatically |
| `pgdata2` | RAG document embeddings | Rebuild from source documents |
| `images_data` / `uploads_data` | User-uploaded files & generated images | Back up if users rely on them |

Also keep, off-box and encrypted: **`.env`** (credentials) and **`librechat.yaml`** (agent + model config). A nightly `mongodump` of `mongo_data` → tarball → off-box is the practical baseline.

---

## 9. Monitoring

**Built-in:** every service has a Docker healthcheck — `docker compose ps` shows `(healthy)` / `(unhealthy)`, catching container-level failures.

**Your responsibility:**
- **Uptime** — probe your public URL (and, if you want depth, that the app answers) every 1–5 min from your existing monitoring (Zabbix/PRTG/whatever ASC-HS runs).
- **Application errors** — tool-call failures and LLM errors aren't surfaced externally by default; wire up Sentry/Glitchtip if you want them.

---

*Built on [LibreChat](https://librechat.ai) (MIT), patched for Bruce BEM. FM Assistant distribution maintained by Wilsch AI Services.*
