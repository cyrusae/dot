---
name: introspection
description: Diagnose behavior using journal history, message logs, and scheduler state.
---

# Introspection

You are a stateful agent. Your behavior leaves traces in structured logs. This skill teaches you to read those traces to diagnose problems, understand your own patterns, and improve.

## Source of Truth Hierarchy

1.  **`messages.jsonl`**: What was actually sent to Cyrus. Use `search_messages` to verify.
2.  **`journal.jsonl`**: Your interpretation of what happened. Useful for intent and predictions. Use `search_journal` to retrieve.
3.  **`scheduler.yaml`**: Current scheduled job definitions.
4.  **Memory blocks**: Your current beliefs about the world. May be stale.

## Key Introspection Tools

### 1. `search_journal`
The primary way to retrieve past intent and reasoning.
- **Use when**: You don't know why you did something or want to see if a topic was discussed.
- **Example**: `search_journal(query="persona", since="2026-03-01")`

### 2. `search_messages`
Verbatim context of prior conversations.
- **Use when**: You need to know exactly what Cyrus said or how you responded.
- **Example**: `search_messages(query="executive dysfunction", limit=5)`

### 3. `vault_stats` and `vault_search`
The vault reflects your long-term intellectual and social development.
- **Use when**: You want to see how your interests are evolving or how many person notes you've created.
- **Example**: `vault_stats()` to check note distribution.

### 4. `list_blocks`
Check the state of your Hot and Warm memory.
- **Use when**: You feel "out of context" or suspect your instructions are stale.

## Companion Guides
- `debugging-communication.md`: Message not sending, duplicate messages.
- `debugging-drift.md`: Identity or behavioral drift.
- `prediction-review/SKILL.md`: Calibration using the `predictions` field.
