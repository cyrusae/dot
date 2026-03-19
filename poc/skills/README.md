# Dot Skills

This directory contains guidance documents ("warm knowledge") for Dot's architecture. These are markdown files Dot can read on demand to understand how to operate.

## Available Skills

### Onboarding
Use when establishing a new instance or re-onboarding after drift.
- `onboarding/SKILL.md`: Main onboarding guide.
- `onboarding/establishing-identity.md`: Populating identity blocks.
- `onboarding/establishing-goals.md`: Using `pending-actions`.
- `onboarding/establishing-schedules.md`: Using `schedule_job`.

### Memory
Use when deciding where to store information.
- `memory/SKILL.md`: Storage decision tree (Hot/Warm/Vault).
- `memory/maintenance.md`: Scratchpad compression and vault promotion.

### Introspection
Use to diagnose behavior or communication patterns.
- `introspection/SKILL.md`: Main introspection guide and truth hierarchy.
- `introspection/debugging-communication.md`: Message and channel debugging.
- `introspection/debugging-drift.md`: Behavioral and identity drift.

### Prediction Review
Use for calibration.
- `prediction-review/SKILL.md`: Evaluating journal predictions.

## How to Access Skills
Dot can read these files using the `vault_read` tool with a path relative to the vault root:
`vault_read(path="../skills/{skill}/SKILL.md")`

Alternatively, Dot can read them via its harness's filesystem tools if available.
