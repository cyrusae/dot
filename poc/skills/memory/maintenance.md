# Memory Maintenance

Memory blocks that get too large create noise. Stale information in the vault wastes search resources.

## Regular Maintenance Ticks
Use an `operational_check` tick (or your `weekly-reflection`) to perform these:

### 1. Scratchpad Compression
If `active-scratchpad` exceeds ~500 tokens, it's time to compress.
- **Archive to Vault**: Move completed work or stable observations to `vault_write` notes (type: `scratchpad`).
- **Clean up**: Use `write_block` to clear the scratchpad of old session content.

### 2. Pending Actions Consolidation
Review `pending-actions`.
- **Remove completed items**.
- **Promote to Vault**: If an intention is actually a long-term project, create a `type: research-note` in the vault and link to it.
- **Re-prioritize**: If items are piling up, reflect on why (executive dysfunction support or your own drift?).

### 3. Journal Review
Use `search_journal` to look at patterns.
- Are you hitting your `predictions`? (See `prediction-review` skill).
- Are your `agent_did` entries actually meaningful?

### 4. Vault Promotion
Audit your seed notes (status: `seed`) using `vault_search` or `vault_stats`.
- When a note has 2-3 `vault_append` entries, consider promoting it to `status: developing` and organizing its content.

## Health Metrics
Use `vault_stats` to see note counts by type. If you have 50 `scratchpad` notes but zero `reflection` notes, your memory is purely task-oriented. This is a signal for identity drift.
