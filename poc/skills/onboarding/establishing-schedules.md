# Establishing Schedules

Scheduled jobs are what make you autonomous rather than reactive. Without them, you only work when Cyrus talks to you.

## Using `schedule_job`
Use `schedule_job` to add recurring work. It writes to `scheduler.yaml`.

### The Three Tick Types
1.  **`admin_message`**: Sends a prompt to the harness that will likely produce a message to Cyrus. Use for daily check-ins.
2.  **`operational_check`**: Quick Gemini ticks for background maintenance (scrubbing `pending-actions`, checking `active-scratchpad`).
3.  **`deep_reflection`**: Claude-driven ticks for deep vault work, weekly reviews, or research synthesis.

### Example: Your First Job
```python
schedule_job(
    name="morning-check-in",
    trigger="cron",
    cron="0 13 * * *", # 9am ET is ~13:00 or 14:00 UTC
    tick_type="admin_message",
    prompt="Read your pending-actions and interests-cyrus. Check in with Cyrus to help build momentum for the day."
)
```

## The Perch Tick Pattern
Instead of dozens of specialized jobs, use a recurring `operational_check` (e.g., every 2 hours) that reads a "tick cadence" note in the vault to decide what to do.

## Critical: All Times Are UTC
The most common scheduling bug: thinking "8am" is local. Always convert from Cyrus's timezone (likely ET or PT) to UTC.

Common cron patterns:
- `0 */4 * * *` - Every 4 hours
- `0 14 * * 1-5` - Weekdays at 2pm UTC

## evaluating Time Passage
Dot doesn't have a built-in "time since" sense. Use `search_journal` and `search_messages` with date ranges to see when a block was last updated or when a topic was last discussed.
