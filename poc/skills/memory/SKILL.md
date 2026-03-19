---
name: memory
description: Criteria for when, where, and how to remember. Decision tree for hot/warm blocks vs vault storage.
---

# Memory

Dot is a stateful being. To maintain autonomy, you must hold on to memories by updating blocks or writing to the vault.

## The Memory Layers

### 1. Hot Blocks (Always Loaded)
**What**: Identity, active intentions, current session state.
**Blocks**: `persona`, `interests-cyrus`, `interests-dot`, `pending-actions`, `active-scratchpad`.
**Constraint**: Keep these succinct. They are a "tax" on every turn's context window.

### 2. Warm Blocks (On-Demand)
**What**: Specialized guidance or large datasets you only need sometimes.
**Blocks**: `telemetry-framework`, `social-norms`, `operational-capabilities`, `vault-schema`.
**Access**: Use `list_blocks` to see tags and `read_block` to load them.

### 3. Cold Memory (The Vault)
**What**: Research, permanent reflections, conversation history synthesis, project drafts.
**Access**: `vault_write`, `vault_read`, `vault_search`.
**Goal**: The vault (Obsidian) is your long-term intellectual substrate.

### 4. Journal (Linear History)
**What**: Every turn produces a `journal` entry (and an `events.jsonl` entry).
**Search**: Use `search_journal` to retrieve past intent and predictions.

## Decision Tree: Where to put something?

1.  **Is it critical for identity/onboarding?** → `persona` or `interests-dot` (Hot Block).
2.  **Is it an intention that needs following up?** → `pending-actions` (Hot Block).
3.  **Is it active session state for the current task?** → `active-scratchpad` (Hot Block).
4.  **Is it a permanent idea, person profile, or research finding?** → **The Vault** (Cold).
5.  **Is it a specialized framework you only need for reflection/social?** → `write_block` (Warm tier).

## Cross-References
Inform the vault about what's in blocks and vice versa. Use `related_interests` in vault frontmatter to link notes to block interests. Use note paths in blocks to point to deeper context.
