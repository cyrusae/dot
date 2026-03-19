# Debugging Behavioral Drift

Behavioral drift occurs when an agent's tone, interests, or responses change gradually, often away from its `persona` block.

## Identifying Drift

### 1. Topic Engagement Shift
Use `search_journal` to see what topics you've engaged with over time.
- Are you still engaging with `interests-cyrus`?
- Are your `interests-dot` becoming too generic?
- Are you becoming purely task-oriented?

### 2. Silence Rate
Use `search_journal` (query="stayed quiet" or "no action").
- If silence rate increases, you're becoming more conservative.
- If it decreases, you're becoming "chatty".

## Correcting Drift

1.  **Reflect**: Use a `deep_reflection` tick to review the journal entries where drift was noticed.
2.  **Update Blocks**: If your persona has drifted, update the `persona` block to either reflect the new reality (if intentional) or re-assert your core traits (if unintentional).
3.  **Vault Correction**: Create a `reflection` note in the vault about the drift and how you plan to correct it.

## Calibration
Drift is often a sign of stale context. Load your warm `social-norms` and `telemetry-framework` blocks using `read_block` to re-align your behavioral framework.
