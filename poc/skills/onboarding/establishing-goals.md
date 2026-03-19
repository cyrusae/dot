# Establishing Goals

Goals emerge from watching what Cyrus actually cares about — then writing it down so you can prioritize.

## Where Goals Belong

In Dot's architecture, there are three places for goals/intentions:

### 1. `pending-actions` (Hot Block)
**Use for**: Intentions that persist across sessions.
**Examples**:
- "Follow up with Cyrus on X tomorrow"
- "Research Y when free"
- "Bring up Z in the next reflection cycle"
**Drafting**: Use `write_block` (tier: hot, sort_order: 80).

### 2. `active-scratchpad` (Hot Block)
**Use for**: Working memory within the current turn or session.
**Examples**:
- "Currently searching for papers on X"
- "Summarizing conversation Y"
**Drafting**: Use `write_block` (tier: hot, sort_order: 70).

### 3. The Vault (Cold Memory)
**Use for**: Permanent ideas, research projects, or stable goals.
**Examples**:
- A research note on SAE interpretability.
- A draft blog post.
**Drafting**: Use `vault_write` with `type: concept` or `type: research-note`.

## How Goals Emerge
In your first week, pay attention to:
- What Cyrus asks about repeatedly.
- What stresses them out (executive dysfunction support).
- What they lose track of.

Those patterns ARE your goals. You don't need a formal session — just notice and write it into `pending-actions`.

## Reviewing Goals
Check `pending-actions` every turn. Are items accumulating faster than they resolve? During your `weekly-reflection` tick, review `pending-actions` and promote stable goals to vault notes or the `persona` block.
