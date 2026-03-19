# Obsidian Sidecar Spec: Indexed Vault Access for AI Agent

## Purpose

Run Obsidian as a sidecar container in a K3s pod to provide an AI agent (Letta framework, Claude LLM) with indexed vault operations — full-text search, backlink resolution, frontmatter queries, and tag filtering — via a local REST API. The agent's primary knowledge store is an Obsidian-compatible vault of markdown files on a persistent volume.

## Why a sidecar instead of raw file operations

Obsidian maintains a pre-built search index over vault contents. Querying this index returns results in ~0.3s with ~100 tokens of context, versus scanning files directly which costs ~2s and potentially millions of tokens for discovery operations (backlinks, orphan detection, tag queries) on a vault of several thousand notes. For an AI agent doing interdisciplinary research with a token-based cost budget, indexed queries can reduce search/discovery costs by 1-2 orders of magnitude. The index also provides graph-aware features (backlinks, orphans, resolved wikilinks) that are expensive to replicate with filesystem parsing.

## Architecture

```
┌─────────────────────── K3s Pod ───────────────────────┐
│                                                        │
│  ┌──────────────┐     REST API      ┌───────────────┐ │
│  │ Letta Agent   │ ───────────────► │ Obsidian       │ │
│  │ (main container) │  localhost:27124 │ (sidecar)      │ │
│  └──────────────┘                   └───────────────┘ │
│         │                                  │           │
│         └──────────── PVC ─────────────────┘           │
│                   /vault (shared)                       │
└────────────────────────────────────────────────────────┘
```

Both containers mount the same persistent volume claim at `/vault`. The agent writes markdown files; Obsidian indexes them and serves queries over HTTP.

## Sidecar Container

### Base image

`lscr.io/linuxserver/obsidian:latest` (LinuxServer.io)

This runs Obsidian Desktop inside a container with KasmVNC for remote access. The VNC interface isn't needed for API access but comes with the image. Expect ~450MB RAM usage.

### Environment variables

```yaml
env:
  - name: PUID
    value: "1000"
  - name: PGID
    value: "1000"
  - name: TZ
    value: "America/New_York"  # adjust to your timezone
```

### Required Obsidian plugin

**Local REST API** by Adam Coddington (`coddingtonbear/obsidian-local-rest-api`)

This plugin exposes Obsidian's vault operations as an HTTPS REST API on port 27124. It must be installed and enabled inside the running Obsidian instance. On first boot, you'll need to either:

1. **Manual setup (one-time):** Connect to the KasmVNC interface (default port 3000), open the vault at `/vault`, install the community plugin "Local REST API", enable it, and note the API key it generates. Subsequent container restarts will preserve the config if the vault PVC includes the `.obsidian/` directory.

2. **Pre-seeded config:** Include the plugin files and config in the vault's `.obsidian/` directory on the PVC before first boot. The plugin lives at `.obsidian/plugins/obsidian-local-rest-api/` and needs `main.js`, `manifest.json`, and `data.json` (containing the API key and settings). Also ensure `.obsidian/community-plugins.json` lists `"obsidian-local-rest-api"`.

Option 2 is preferred for reproducible deployments. You can set this up once via the GUI, then the `.obsidian/` directory persists on the PVC.

### API key

The Local REST API plugin generates an API key on first enable. Store this as a K8s secret and inject it into the Letta container as an environment variable. All API calls require the header:

```
Authorization: Bearer <API_KEY>
```

### Ports

| Port | Purpose | Exposure |
|------|---------|----------|
| 27124 | Local REST API (HTTPS) | Pod-internal only (localhost) |
| 3000 | KasmVNC web interface | Optional: expose via NodePort/Ingress for initial setup and debugging |

The REST API uses a self-signed cert by default. The agent should either skip TLS verification for localhost calls or configure the plugin to use HTTP (available in plugin settings).

## Persistent Volume Claim

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: dot-vault
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 5Gi  # adjust based on expected vault size; 5Gi is generous for text-only
```

Mount path in both containers: `/vault`

The PVC holds:
- Markdown notes (Dot's knowledge base)
- `.obsidian/` directory (Obsidian config, plugin data, index cache)
- Symlinked or copied content from other sources (e.g., alcanzai reading notes)

## REST API: Key Endpoints

The agent needs tool implementations that call these endpoints. Base URL: `https://localhost:27124`

### Vault operations (core agent tools)

| Operation | Method | Endpoint | Notes |
|-----------|--------|----------|-------|
| Read file | GET | `/vault/{path}` | Returns file content |
| Create/overwrite file | PUT | `/vault/{path}` | Body = markdown content |
| Append to file | POST | `/vault/{path}` | Adds content to end |
| Delete file | DELETE | `/vault/{path}` | |
| List files | GET | `/vault/` | Returns directory listing |
| Patch file (insert/replace) | PATCH | `/vault/{path}` | Insert at heading, below content matching pattern |

### Search (indexed, fast)

| Operation | Method | Endpoint | Notes |
|-----------|--------|----------|-------|
| Full-text search | POST | `/search/simple/` | Body: `{"query": "..."}` — uses Obsidian's index |
| JsonLogic query | POST | `/search/` | Structured queries on frontmatter, tags, paths |
| Dataview DQL | POST | `/search/dataview/` | Requires Dataview plugin installed |

### Active file context

| Operation | Method | Endpoint | Notes |
|-----------|--------|----------|-------|
| Open file in Obsidian | POST | `/open/{path}` | Useful for debugging via VNC |
| Get active file | GET | `/active/` | Returns currently open file |

### Periodic notes

| Operation | Method | Endpoint | Notes |
|-----------|--------|----------|-------|
| Current periodic note | GET | `/periodic/{period}` | period = daily/weekly/monthly/quarterly/yearly |

## Health Check

The REST API serves a root endpoint. Use this for the sidecar's readiness probe:

```yaml
readinessProbe:
  httpGet:
    path: /
    port: 27124
    scheme: HTTPS
  initialDelaySeconds: 30  # Obsidian takes time to boot and index
  periodSeconds: 10
```

The initial delay matters — Obsidian needs to start, load the vault, build/update the index, and initialize plugins. For a large vault, this could take 30-60 seconds. The Letta container should wait for the sidecar to be ready before issuing API calls.

## Agent Tool Implementation Mapping

These are the Letta tool calls the agent uses, mapped to REST API calls:

```
vault_read(path)        → GET    /vault/{path}
vault_write(path, content) → PUT    /vault/{path}
vault_append(path, content) → POST   /vault/{path}
vault_delete(path)      → DELETE /vault/{path}
vault_list(directory?)   → GET    /vault/ or /vault/{dir}/
vault_search(query)     → POST   /search/simple/
vault_query(jsonlogic)  → POST   /search/
```

Each tool call is a thin HTTP wrapper. The agent sends a short request and receives structured results — it never needs to scan files in its own context window for discovery operations.

## Optional: Additional Obsidian Plugins

These are not required but add useful capabilities:

- **Dataview**: Enables structured queries over frontmatter (DQL endpoint). Highly recommended if the vault uses structured frontmatter for note metadata (source type, tags, connection strength, creation date).
- **Templater**: Template-based note creation. Useful if the agent follows a consistent note format.
- **Graph Analysis**: Exposes graph metrics. Interesting for the agent to understand its own knowledge topology.

Install via the VNC interface on first setup; they persist in `.obsidian/plugins/` on the PVC.

## Resource Expectations

| Resource | Estimate | Notes |
|----------|----------|-------|
| RAM | 400-600MB | Varies with vault size and plugin count |
| CPU | Low idle, spikes on reindex | Index updates are incremental after initial build |
| Disk | Vault size + ~50MB for index/config | The index is a small fraction of vault size |
| Network | Pod-internal only | No external traffic unless syncing |

## Deployment Sequence

1. Create the PVC (`dot-vault`)
2. Deploy the Obsidian sidecar with VNC port exposed
3. Connect via VNC, open `/vault` as vault, install Local REST API plugin (+ Dataview if desired)
4. Note the generated API key, store as K8s secret
5. Close VNC port exposure (optional, or keep for debugging)
6. Deploy the Letta agent container in the same pod, mounting the same PVC
7. Configure agent tool calls to hit `https://localhost:27124` with the API key
8. Verify with a simple `vault_list()` call

After initial setup, the pod can restart without repeating steps 2-4 — the `.obsidian/` config persists on the PVC.

## Upgrade Path

- **Start without the sidecar**: The agent can use raw file tools against the PVC while you get the sidecar running. The vault is just markdown files either way.
- **Add Obsidian Sync later**: If you want to browse the vault on personal devices via Obsidian's native app, add Obsidian Headless (`npm install -g obsidian-headless`) as a sync daemon. Requires Sync subscription ($4/month).
- **Scale the index**: If the vault grows very large (10k+ notes), monitor Obsidian's memory usage and consider bumping the sidecar's resource limits.

## Security Notes

- The REST API is pod-internal (localhost only) — not exposed to the cluster network unless you create a Service for it.
- The API key provides authentication. Rotate it if compromised (regenerate in plugin settings via VNC).
- The self-signed TLS cert is fine for pod-internal traffic. Don't expose port 27124 externally without proper TLS termination.
- The KasmVNC interface has its own auth. Change the default credentials if you keep it exposed.