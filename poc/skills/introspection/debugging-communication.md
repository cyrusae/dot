# Debugging Communication Patterns

## Common Problems

### Silent Failure (Agent Ran But Sent Nothing)
**Symptoms**: Turn starts but no message reaches Cyrus.
- **Diagnosis**: Use `search_journal` for the session's timestamp. Did the `agent_did` field say you were going to send a message, or did you stay quiet?
- **Root Cause**: Often a decision in the `social-norms` block to "stay quiet" or the harness routing choosing not to engage.

### Duplicate Messages
**Symptoms**: The same message appears twice in Cyrus's inbox.
- **Diagnosis**: Use `search_messages` to see if multiple entries have the same `timestamp`.
- **Root Cause**: Overlapping schedules in `scheduler.yaml` (e.g., two ticks at 09:00) or an external process re-triggering the turn.

### Message Sent with Wrong Context
**Symptoms**: The message mentions outdated information from blocks.
- **Diagnosis**: Use `list_blocks` to see when blocks were last modified. Use `search_journal` to see if a prior turn was supposed to update the block but failed.
- **Root Cause**: Stale blocks.

## Pattern Analysis
Use `search_messages` to look at how often you're speaking.
- **Chatty Sessions**: Many messages in a short window. Are they all necessary?
- **Engagement Audit**: Use `search_journal` to see what topics (`interests-dot`, `interests-cyrus`) trigger the most interaction.
- **Executive Dysfunction Support**: Are you providing enough momentum in `admin_message` ticks?
