---
name: prediction-review
description: Evaluate prior journal predictions to calibrate behavior.
---

# Prediction Review

Predictions in the `journal` field are your calibration backbone. They are NOT about being right — they are about identifying gaps in your understanding of the world.

## Philosophy
When you miss a prediction:
1.  **Identify what you got wrong**.
2.  **Update a memory block or vault note** with the new insight.
3.  **Trace the wrong assumption** back to a specific instruction.

## Context Categories

1.  **Collaborative** (you're directly involved): Should be ~90-100% accurate. If not, your self-model is flawed.
2.  **Observational** (Cyrus's responses): Should be ~50-70%. This is the target for calibration.
3.  **Infrastructure** (scheduler, platform): Should be ~50%. Depends on factors outside your awareness.

## Review Workflow

1.  **Retrieve candidates**: Use `search_journal` with a date range (2-3 days ago).
2.  **Gather evidence**: Use `search_messages` to see what actually happened.
3.  **Evaluate**: Decide if each prediction was `true` or `false`.
4.  **Log Outcome**: Use `vault_write` to create a `type: reflection` note for the calibration cycle.

```yaml
---
type: reflection
status: seed
tags: [calibration, prediction-review]
---
# Prediction Review Cycle: [Date]
- Prediction: "Cyrus will ignore the SAE paper"
- Result: FALSE (Cyrus engaged for 30 minutes)
- Miss: Cyrus's interest in SAE is deeper than `interests-cyrus` suggests.
- Action: Update `interests-cyrus` with SAE sub-topics.
```

## The Loop
A review that doesn't change a block or file is just bookkeeping. If you haven't updated anything in two weeks after a prediction-review, you're not learning.
