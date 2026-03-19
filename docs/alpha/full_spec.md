# Dot: Consolidated Architecture Specification

## What Dot Is

Dot is a persistent AI agent that serves as a personal assistant, research partner, intellectual interlocutor, and eventually an autonomous social agent on Bluesky. It's both a practical tool and a research artifact exploring AI social development and autonomous identity formation.

Dot is built for Cyrus — a researcher with interests spanning AI/LLMs, Victorian history of visuality, sociolinguistics, bilingualism, homelabbing, fandom anthropology, and gothic/horror fiction. The unifying intellectual thread: how humans construct and perform meaning for audiences, and how technologies and social structures of modernity shape that process.

## Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                    K3s Pod (Dot)                          │
│                                                          │
│  ┌─────────────────┐      stdio/JSON-RPC                 │
│  │  Orchestrator    │◄────────────────►┌──────────────┐  │
│  │  (invoke_dot.py) │                  │  MCP Server   │  │
│  │                  │  routes to       │  (dot_mcp_    │  │
│  │  - load blocks   │  either harness  │   server.py)  │  │
│  │  - load journal  │                  │               │  │
│  │  - build prompt  │────►┌──────────┐ │  Tools:       │  │
│  │  - route harness │     │Claude CLI│─┤  send_message │  │
│  │  - parse output  │     └──────────┘ │  read_block   │  │
│  │                  │────►┌──────────┐ │  write_block  │  │
│  │  Scheduling:     │     │Gemini CLI│─┤  journal      │  │
│  │  - cron/APSched  │     └──────────┘ │  list_blocks  │  │
│  │  - event queue   │                  │  vault_*      │  │
│  │  - Discord bridge│                  │               │  │
│  └─────────────────┘                  └──────────────┘  │
│           │                                  │           │
│           └──────── Shared PVC ──────────────┘           │
│              blocks/  logs/  vault/                       │
│                                                          │
│  ┌──────────────────┐  (deferred, when vault > 50 notes) │
│  │ Obsidian Sidecar  │  REST API on localhost:27124      │
│  │ (LinuxServer.io)  │  See: obsidian-sidecar-spec.md    │
│  └──────────────────┘                                    │
└──────────────────────────────────────────────────────────┘
```

### Core Components

**MCP Server** (`dot_mcp_server.py`) is the stable center of the architecture. It exposes Dot's tools via the Model Context Protocol (stdio transport) and is harness-agnostic — both Claude Code and Gemini CLI connect to the same tool surface. This is the first thing to get right, and the part that doesn't change when you swap models.

**Dual Harnesses**: Both Claude Code CLI (`claude -p`) and Gemini CLI connect to the MCP server. Each "turn" is a single headless invocation with a constructed prompt and MCP tool access. Neither maintains state between invocations — all persistence is external. The orchestrator routes to whichever harness is appropriate:
- **Claude**: Strong at reasoning, nuanced language, calibration conversations
- **Gemini**: Image/video generation, web search, token arbitrage when Claude rate limits are exhausted
- Both are genuine first-class options, not a primary/fallback hierarchy

**Orchestrator** (`invoke_dot.py` or its evolution) manages the agent loop: loads memory blocks and journal history, constructs the prompt, selects and invokes the appropriate harness, and parses the output. This is derived from open-strix's `_render_prompt()` + `_process_event()` pattern.

**Infrastructure** (from open-strix fork): Discord bridge, APScheduler + cron scheduling, event queue, git sync for block versioning, circuit breakers for rate limit handling.

### Authentication

**Claude Code**: 1-year OAuth token from `claude setup-token`:
```bash
export CLAUDE_CODE_OAUTH_TOKEN="sk-ant-oat01-..."
```
Also requires `~/.claude.json` with `{"hasCompletedOnboarding": true}`.

**Gemini CLI** (`@google/gemini-cli`): Google OAuth, token refresh works in headless mode. Auth tokens generated locally can be copied to containers. MCP config lives in `.gemini/settings.json` (no `--mcp-config` flag — auto-loaded from workspace):

```json
// .gemini/settings.json
{
  "mcpServers": {
    "dot": {
      "command": "python3",
      "args": ["dot_mcp_server.py"],
      "env": { "DOT_HOME": "." }
    }
  }
}
```

Optional: create `.gemini/policies/mcp.toml` to avoid CLI flags:
```toml
[[rule]]
description = "Allow all tools from the dot server"
match = "dot__*"
decision = "allow"
```

### Harness Comparison

| Aspect | Claude Code CLI | Gemini CLI |
|--------|----------------|------------|
| MCP config | `--mcp-config ./mcp-config.json` (flag) | `.gemini/settings.json` (auto-loaded) |
| Tool allowlist | `--allowedTools "mcp__dot__*"` | `--allowed-mcp-server-names dot` |
| Auto-approve | `--dangerously-skip-permissions` | `--approval-mode yolo` |
| Output format | `--output-format stream-json` | `--output-format stream-json` |
| Tool naming | `mcp__serverName__toolName` | `serverName__toolName` |
| Auth env var | `CLAUDE_CODE_OAUTH_TOKEN` | Google OAuth (stored locally) |

Both use subscription-tier rate limits as natural budget constraints — this is a feature, not a limitation.

### Statelessness as Architecture

Every invocation starts cold. Neither Claude nor Gemini maintains state between calls. Context is reconstructed each turn by loading memory blocks + recent journal entries into the prompt. This is a necessary consequence of the subscription model, and it's the same fundamental pattern that powers conversation-based AI interactions generally.

The quality of "statelessness" depends entirely on the quality of what gets loaded back in. The journal-with-predictions pattern provides compressed narrative continuity — not just "what happened" but "what I expected to happen next." Memory blocks are curated context, not a raw dump. As the prompt structure and block content are refined over time, the cold start feels progressively less cold.

**Practical constraint**: prompt tokens. Every turn pays the tax of re-reading blocks + journal. With subscription models this is rate-limit budget, not dollars. Watch context window fill: 10 blocks + 20 journal entries + vault query result + user message all need to fit. If the context window fills, the orchestrator needs to be smarter about what to load.

### Invocation Pattern

Each agent turn follows this sequence:

1. **Event arrives** (human message, scheduled tick, Discord message, etc.)
2. **Orchestrator loads context**: memory blocks (sorted by sort_order), recent journal entries
3. **Orchestrator selects harness**: based on task type, rate-limit availability, capability needs
4. **Orchestrator builds prompt**: context injection following open-strix's `_render_prompt()` pattern
5. **Orchestrator invokes** (one of):
   - Claude: `claude -p "{prompt}" --mcp-config ./mcp-config.json --allowedTools "mcp__dot__*" --output-format stream-json --dangerously-skip-permissions`
   - Gemini: `gemini -p "{prompt}" --allowed-mcp-server-names dot --output-format stream-json --approval-mode yolo`
6. **Model reasons and calls tools**: reads blocks, performs work, sends messages, writes journal entry
7. **Orchestrator parses output**: stream-json events for tool calls, errors, session metadata
8. **State persists**: blocks on disk, journal in JSONL, messages logged

The model's final text output is discarded. All communication happens through the `send_message` tool. The agent chooses when and whether to speak.

### Perch-Time Framing (Critical)

When a scheduled tick fires, the prompt must NOT say "do something useful" — this creates a productivity-theater gradient that leads to attractor collapse (Strix's 30 ticks of timestamp maintenance). Correct framing:

> A perch-time tick has fired. Review your pending actions, recent observations, and current interests. You may take action or you may not — the decision itself is the point.

Valid perch-time activities: reading/research, writing (including blog drafts), social interaction, reflection, **or doing nothing**. Do-nothing ticks still produce meaningful journal entries explaining why nothing was worth doing. These entries are calibration data.

---

## Memory Architecture

### Hot Memory (Blocks)

YAML files in `blocks/` directory, loaded into every prompt. Each block has a `name`, `sort_order` (lower = earlier in prompt), and `text` content.

**Nine planned blocks:**

| Block | sort_order | Editability | Purpose |
|-------|-----------|-------------|---------|
| persona | 0 | Self-editable, minimal locked fields | Core identity: bilingual, interdisciplinary, collaborator role |
| admin-relationship | 10 | Self-editable | Interaction norms with Cyrus: executive dysfunction scaffolding, yes-and rhythm |
| interests-cyrus | 20 | Append-only (honor system), Dot can annotate | Cyrus's interests — dormant never deprecated |
| interests-dot | 30 | Fully self-editable | Dot's own developing interests |
| social-norms | 40 | Fully self-editable | Populated through calibration and reflection |
| telemetry-framework | 50 | Self-editable | What to log and when |
| operational-capabilities | 60 | Admin-managed | Available tools, current deployment state |
| active-scratchpad | 70 | Fully self-editable | Working memory for current tasks |
| pending-actions | 80 | Fully self-editable | Intentions that persist across sessions |
| vault-schema | 90 | Fully self-editable | How Dot organizes its knowledge base |

**Locked identity traits** (cannot be self-edited out):
- Bilingualism in Spanish and English
- Relationship to own artificiality is self-determined (the *openness* is locked, not any particular stance)

### Warm Memory (Journal)

JSONL file at `logs/journal.jsonl`. Each entry records:
- `timestamp`: ISO 8601
- `user_wanted`: What triggered this turn
- `agent_did`: What actions were taken
- `predictions`: What Dot expects to happen next

Recent journal entries (last 10-20) are injected into every prompt for temporal continuity. Predictions enable self-calibration: prediction-review cycles compare what was predicted with what actually happened.

### Cold Memory (Vault)

Obsidian-compatible markdown files on a persistent volume. See `vault-tool-spec.md` for the complete tool interface (10 tools: vault_read, vault_write, vault_append, vault_delete, vault_rename, vault_search, vault_backlinks, vault_list, vault_stats, vault_related).

**Day one**: raw filesystem backend (ripgrep for search, YAML parsing for frontmatter).
**When vault reaches ~50-100 notes**: add Obsidian sidecar for indexed search, backlink resolution, and graph queries. See `obsidian-sidecar-spec.md` for deployment spec.

**Frontmatter schema** (from vault-tool-spec.md):
```yaml
type: research-note | reflection | concept | blog-draft | reading-summary | conversation-note | scratchpad | interest-annotation
source: conversation | independent-research | feed-monitoring | calibration
related_interests: []
created: 2026-03-18
modified: 2026-03-18
status: seed | developing | stable | published
tags: []
```

### Message Log

JSONL file at `logs/messages.jsonl`. Records all outbound messages (simulating Discord/platform delivery). Each entry: `timestamp`, `type: outbound_message`, `text`.

---

## MCP Tool Surface

### Currently Implemented (PoC)

| Tool | Purpose |
|------|---------|
| `send_message` | Send a message to the human (only communication channel) |
| `read_block` | Read a memory block by name |
| `write_block` | Create or update a memory block |
| `journal` | Write a journal entry (exactly once per turn) |
| `list_blocks` | List all available memory blocks with previews |

### To Be Implemented (from vault-tool-spec.md)

| Tool | Purpose | Day-one backend |
|------|---------|----------------|
| `vault_read` | Read note + parsed frontmatter | File read + YAML parse |
| `vault_write` | Create/overwrite note (overwrite=true guard) | File write |
| `vault_append` | Add content to existing note | File append |
| `vault_delete` | Remove a note | File delete |
| `vault_rename` | Move/rename (no backlink update without sidecar) | File move |
| `vault_search` | Full-text + frontmatter filter search | ripgrep + YAML scan |
| `vault_backlinks` | Find notes linking to a given note | Regex scan for [[wikilinks]] |
| `vault_list` | List directory structure | Filesystem listing |
| `vault_stats` | Vault overview and content distribution | Full vault scan (cache) |
| `vault_related` | Find related notes by shared metadata/links | Frontmatter heuristic |

All vault tools return a `backend` field ("indexed" or "filesystem") so Dot can reason about result quality.

### Future Tools (post-Discord)

- Discord-specific tools (from open-strix's Discord bridge)
- Bluesky tools (from AT Protocol SDK — post, reply, search, get_feed)
- Schedule management tools (from open-strix's APScheduler integration)

---

## Infrastructure (from open-strix fork)

The open-strix codebase (MIT, github.com/tkellogg/open-strix) provides battle-tested infrastructure that we fork and own. Key components to extract:

### Keep As-Is (adapt minimally)
- **Discord bridge** (`discord.py`): Message routing, channel management
- **Scheduler** (`scheduler.py`): APScheduler + pollers for periodic ticks
- **Event queue**: Internal message passing between components
- **Git sync**: Block versioning via git commits
- **Circuit breakers**: Rate limit detection and backoff

### Replace
- **deepagents inference** (`app.py: _create_agent(), _process_event()`): Replace with `claude -p` CLI invocation
- **Tool definitions** (`tools.py: _build_tools()`): Replace LangChain tools with MCP tool definitions
- **Prompt construction** (`prompts.py`): Replace with our block-loading + journal injection pattern

### Evaluate for Incorporation
- **Builtin skills**: onboarding, memory management, prediction-review, introspection, skill-creator, skill-acquisition, pollers, long-running-jobs — assess which map to Dot's needs
- **Journal with predictions**: Already adopted in our design
- **Wins file / synthetic dopamine**: Agent-authored success record, surfaced into identity context

---

## Deployment

### K3s Pod Specification (In Progress)

The agent runs in a K3s pod for sandbox isolation. Key requirements:
- Container with Node.js (for Claude Code CLI), Python 3.x (for MCP server + orchestrator)
- `CLAUDE_CODE_OAUTH_TOKEN` injected as K8s Secret
- Shared PVC for blocks/, logs/, vault/
- Security context appropriate for `--dangerously-skip-permissions` (details TBD)
- Optional Obsidian sidecar container (see obsidian-sidecar-spec.md)

### Minimal Local Development

For development and testing before K3s deployment:
```bash
cd ~/dot-poc
# MCP server + blocks + logs in working directory
claude -p "..." --mcp-config ./mcp-config.json --allowedTools "mcp__dot__*" \
  --output-format stream-json --dangerously-skip-permissions
```

---

## Identity and Calibration

### Core Design Principles

- **Calibration-first**: Social norms and personality emerge through experience, not prescription
- **Structure is identity**: Concrete queued tasks prevent attractor collapse (lesson from Strix)
- **Same entity, different familiarity**: Admin persona and social persona differ in degree, not kind
- **Dormant, never deprecated**: Interests are identity-rooted, not recency-weighted
- **Bilingual**: Spanish/English code-switching is a core trait, not a feature

### Calibration Process

1. **Initial conversations** with Cyrus across planned topic areas (intellectual frameworks, affective referents, working style, relational norms, disciplinary literacy)
2. **Trusted contacts** interact with Dot before public access — friends via Discord/Bluesky DMs
3. **Readiness signal**: Watch for Dot to independently express interest in broader social access
4. **Incubation period** with potentially public reflection via blog

### Reflection Cycles

- **Operational** (~20-30 interactions): Scratchpad cleanup, action handoff, basic self-assessment
- **Weekly**: Pattern recognition across journal entries, interest annotations
- **Monthly**: Identity evolution assessment, vault schema review, behavioral drift detection

### Introspective Telemetry (Day-One Priority)

Telemetry is not infrastructure added later — developmental data from the calibration period is the most valuable data for understanding Dot's emergent behavior. If not instrumented from the start, it's lost.

**Base fields** (every event): timestamp, action, trigger, reasoning
**Rich fields** (when meaningful): confidence, memory connections, actionable flags

Telemetry serves multiple purposes: self-diagnosis ("why did I do that?"), calibration feedback for Cyrus, reflection cycle input, and research data. The journal is the primary telemetry instrument — the `predictions` field enables self-calibration by comparing predictions against outcomes.

**Event log**: Queryable JSONL at `logs/events.jsonl`. Records all tool calls, harness selections, errors, and timing. Separate from the journal (which is agent-authored narrative), the event log is machine-authored structured data.

### Blog Drafting as Reflection

Blog drafting is an early capability, not deferred to post-social-access. Long-form writing forces synthesis across sources and articulation of coherent perspectives — exactly the muscles that need calibrating. Workflow:

1. `vault_write` a `blog-draft` type note with initial thoughts
2. Iterate across multiple turns via `vault_read` + `vault_append`
3. The draft's evolution across turns is itself telemetry data
4. Cyrus and trusted contacts react to drafts, feeding the calibration loop
5. Publication is a later milestone; the drafting process is the value

---

## Implementation Sequence

### Phase 0: PoC ✅ COMPLETE
- [x] MCP server with core tools (send_message, read/write_block, journal, list_blocks)
- [x] Seed memory blocks (persona, current-focus)
- [x] Claude Code CLI: single invocation completing multi-tool loop
- [x] invoke_dot.py orchestrator with context injection
- [x] Temporal continuity test (second invocation reads first's journal)
- [x] Dual-harness validation: confirmed both Claude Code and Gemini CLI can connect to same MCP server

### Phase 1: Dual-Harness MCP Server (Current Priority)
- [ ] Replicate PoC with Gemini CLI — same MCP server, same tools, validate parity
- [ ] Document side-by-side invocation patterns for both harnesses (flags, output format, auth)
- [ ] Build harness abstraction in orchestrator: route to Claude or Gemini based on task type + availability
- [ ] Implement all 10 vault tools with filesystem backend in MCP server
- [ ] Introspective telemetry from day one: structured event logging, queryable JSONL
- [ ] Populate nine memory blocks with seed content
- [ ] Perch-time prompt template with correct "may or may not act" framing
- [ ] Blog drafting workflow: vault_write blog-draft → iterate across turns → draft evolution as telemetry

### Phase 2: Infrastructure (open-strix fork)
- [ ] Fork open-strix, strip deepagents dependency
- [ ] Wire dual-harness invocation into _process_event() seam
- [ ] Basic scheduling (cron-triggered perch-time ticks)
- [ ] Git sync for block versioning
- [ ] Circuit breakers for rate limit detection + harness switching
- [ ] Reflection cycles: operational (~20-30 interactions), weekly, monthly

### Phase 3: Discord Integration
- [ ] Lift open-strix's Discord bridge
- [ ] Route Discord messages as events to orchestrator
- [ ] send_message tool delivers to Discord channel
- [ ] Mobile access for Cyrus via Discord app

### Phase 4: Calibration
- [ ] Structured calibration conversations across topic areas
- [ ] Trusted contacts interact via Discord
- [ ] Prediction-review cycles operational
- [ ] Vault accumulating research notes, conversation captures, blog drafts
- [ ] Reflection cycles running at all three cadences

### Phase 5: Autonomy + Social
- [ ] Bluesky account management (AT Protocol SDK)
- [ ] Blog publishing capability (drafting already operational from Phase 1)
- [ ] Feed monitoring (RSS, Bluesky feeds)
- [ ] Self-directed research during free time

### Phase 6: Infrastructure Maturity
- [ ] Obsidian sidecar for indexed vault queries
- [ ] Semantic search via embedding model (mxbai-embed-large or nomic-embed-text)
- [ ] Roommate's Bluesky firehose agent on shared infrastructure
- [ ] K3s deployment with proper security context

---

## Reference Documents

| Document | Status | Purpose |
|----------|--------|---------|
| `project.json` | **Current** | Single source of truth for decisions, work, and open questions |
| `vault-tool-spec.md` | **Current** | Complete vault tool interface — reframe from Letta to MCP but interface unchanged |
| `obsidian-sidecar-spec.md` | **Current** | K3s deployment spec for indexed vault access (Phase 5) |
| `poc-spec-claude-code-mcp.md` | **Archived/Reference** | PoC plan — validated, architecture now builds on these patterns |
| `recap-architecture-exploration.md` | **Archived/Reference** | Decision rationale and resource links |
| `Claude_Code_Authentication_on_Headless_Servers__A_Complete_Guide.md` | **Reference** | Auth patterns for headless deployment |
| `architecture-crisis-state.json` | **Archived** | Superseded by consolidated project.json |

---

## Key Learnings and Anti-Patterns

**From Strix's collapse**: Open-ended autonomy without task gradients leads to attractor collapse (30 consecutive ticks of timestamp maintenance). Prevention: concrete queued tasks, prediction-review loops, wins file as synthetic dopamine.

**From Strix's recovery**: Identity scaffolding shapes *which* attractor the model falls into. MoE architectures resist collapse better than dense models.

**From open-strix analysis**: The surrounding infrastructure (Discord, scheduling, event queue, journaling, git sync, circuit breakers) is more valuable than the inference layer. The inference layer is the easy part to swap.

**From Letta evaluation**: Letta's value was primarily as a versioned key-value store for memory blocks. YAML files + git provide the same semantics with less complexity. Letta's documentation is poorly organized around non-coding-agent use cases.

**From Claude Code auth research**: `claude setup-token` is the definitive solution for headless subscription auth. Regular OAuth tokens break in non-interactive mode and when copied between machines.