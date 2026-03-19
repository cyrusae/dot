"""
Minimal orchestrator that constructs a prompt the way open-strix does
and invokes Claude Code or Gemini CLI headlessly.
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

HOME = Path(__file__).parent
BLOCKS_DIR = HOME / "blocks"
JOURNAL_LOG = HOME / "logs" / "journal.jsonl"
EVENT_LOG = HOME / "logs" / "events.jsonl"
MCP_CONFIG = HOME / "mcp-config.json"
SERVER_SCRIPT = HOME / "dot_mcp_server.py"


def load_blocks() -> tuple[str, str]:
    """Load only hot memory blocks (tier == 'hot' or missing).
    Returns (rendered_blocks_string, scratchpad_text).
    """
    blocks = []
    scratchpad_text = ""
    for path in sorted(BLOCKS_DIR.glob("*.yaml")):
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            tier = loaded.get("tier", "hot")  # Default to hot for backwards compat
            if tier != "hot":
                continue

            name = loaded.get("name", path.stem)
            text = loaded.get("text", "")
            sort_order = loaded.get("sort_order", 0)
            blocks.append((sort_order, name, text))

            if name == "active-scratchpad":
                scratchpad_text = text
        except Exception:
            continue

    blocks.sort(key=lambda b: (b[0], b[1]))
    rendered = []
    for _, name, text in blocks:
        rendered.append(f"memory block: {name}\n{text}")
    return "\n\n".join(rendered) if rendered else "(no blocks)", scratchpad_text


def load_journal(count: int = 10) -> str:
    """Load the last N journal entries."""
    if not JOURNAL_LOG.exists():
        return "(no journal entries)"

    entries = []
    for line in JOURNAL_LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    recent = entries[-count:]
    if not recent:
        return "(no journal entries)"

    rendered = []
    for entry in recent:
        rendered.append(
            f"timestamp: {entry.get('timestamp', '?')}\n"
            f"user_wanted: {entry.get('user_wanted', '')}\n"
            f"agent_did: {entry.get('agent_did', '')}\n"
            f"predictions: {entry.get('predictions', '')}"
        )
    return "\n\n".join(rendered)


def log_event(harness: str, prompt_chars: int, session_id: str, return_code: int, duration_seconds: float) -> None:
    """Log an operational event to logs/events.jsonl."""
    EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    
    event = {
        "timestamp": datetime.now().isoformat(),
        "harness": harness,
        "prompt_chars": prompt_chars,
        "session_id": session_id,
        "return_code": return_code,
        "duration_seconds": round(duration_seconds, 3),
    }
    
    with open(EVENT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def write_session_log(harness: str, prompt: str, session_id: str, messages: list[str], duration: float, return_code: int) -> None:
    """Write a full session log to logs/sessions/ for debugging."""
    try:
        session_dir = HOME / "logs" / "sessions"
        session_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%SZ")
        # Use first 8 chars of session_id for the filename slug
        safe_session_id = str(session_id)[:8] if session_id and session_id != "?" else "unknown"
        filename = f"{timestamp}_{harness}_{safe_session_id}.json"
        
        display_prompt = prompt
        if len(prompt) > 50000:
            display_prompt = prompt[:50000] + "\n... [TRUNCATED 50000+ chars]"
            
        record = {
            "timestamp": datetime.now().isoformat(),
            "harness": harness,
            "session_id": session_id,
            "duration_seconds": round(duration, 3),
            "return_code": return_code,
            "prompt_chars": len(prompt),
            "prompt": display_prompt,
            "messages_sent": messages,
        }
        
        log_path = session_dir / filename
        log_path.write_text(json.dumps(record, indent=2, ensure_ascii=True), encoding="utf-8")
        
        # Log rolling: delete files older than 30 days
        try:
            now = time.time()
            thirty_days_seconds = 30 * 24 * 3600
            for path in session_dir.glob("*.json"):
                if now - path.stat().st_mtime > thirty_days_seconds:
                    path.unlink()
        except Exception:
            pass # Never block/fail on cleanup
            
    except Exception:
        pass # Never fail an invocation due to logging


def build_prompt(event: str, tick_type: str = "admin_message") -> str:
    """Build the full turn prompt with context injection."""
    blocks_str, scratchpad_text = load_blocks()
    journal = load_journal()
    inbox = load_inbox()

    # Scratchpad monitoring
    scratchpad_nudge = ""
    word_count = len(scratchpad_text.split())
    if word_count > 375:
        scratchpad_nudge = "\nNote: Your scratchpad is getting long. During this turn, review it and compress — promote what is worth keeping, discard what is stale.\n"

    # Perch-time templates
    if tick_type == "admin_message":
        current_event_section = f"Current event:\n{event}"
    elif tick_type == "operational_check":
        current_event_section = "Perch-time tick (operational check). Review your pending-actions and active-scratchpad. Is anything stale or ready to act on? You may take action or you may not — the decision itself is the point."
    elif tick_type == "deep_reflection":
        current_event_section = "Perch-time tick (deep reflection). Load your telemetry-framework warm block. Review your recent journal entries and vault activity. Look for patterns across turns. You may take action or you may not — the decision itself is the point."
    else:
        current_event_section = f"Current event:\n{event}"

    sections = []
    sections.append(f"1) Last journal entries:\n{journal}")
    
    if inbox:
        sections.append(f"2) Unread inbox messages:\n{inbox}")
    
    idx = len(sections) + 1
    sections.append(f"{idx}) Hot memory blocks (auto-loaded):\n{blocks_str}{scratchpad_nudge}")
    
    idx = len(sections) + 1
    sections.append(f"{idx}) {current_event_section}")

    sections_str = "\n\n".join(sections)

    return f"""Context for this turn:

{sections_str}

Remember: Use send_message to communicate. Your final text output is discarded.
Call journal exactly once at the end of your turn.
You can read/write the 'routing-state' warm block to express a preferred harness for future turns.
"""


def load_inbox() -> str:
    """Load unread messages from logs/inbox.jsonl."""
    inbox_log = HOME / "logs" / "inbox.jsonl"
    if not inbox_log.exists():
        return ""

    unread = []
    try:
        lines = inbox_log.read_text(encoding="utf-8").splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            if entry.get("read") is not True:
                timestamp = entry.get("timestamp", "?")
                sender = entry.get("from", "Cyrus")
                text = entry.get("text", "")
                unread.append(f"[{timestamp}] from {sender}: {text}")
    except Exception:
        return ""

    return "\n".join(unread) if unread else ""


def read_new_messages(messages_log: Path, prior_size: int) -> list[str]:
    """Return messages written to messages_log after prior_size bytes."""
    if not messages_log.exists():
        return []
    new_content = messages_log.read_bytes()[prior_size:]
    messages = []
    for line in new_content.decode("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            if entry.get("text"):
                messages.append(entry["text"])
        except json.JSONDecodeError:
            continue
    return messages


def invoke_claude(prompt: str) -> None:
    """Invoke Claude Code headlessly with the constructed prompt."""
    start_time = time.time()
    messages_log = HOME / "logs" / "messages.jsonl"
    prior_size = messages_log.stat().st_size if messages_log.exists() else 0

    cmd = [
        "claude", "-p", prompt,
        "--mcp-config", str(MCP_CONFIG),
        "--allowedTools", "mcp__dot__*",
        "--output-format", "json",
        "--dangerously-skip-permissions",
    ]

    print(f"[orchestrator] Invoking claude -p ({len(prompt)} chars)...",
          file=sys.stderr)

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(HOME),
    )

    duration = time.time() - start_time
    session_id = "?"
    
    if proc.stdout:
        try:
            result = json.loads(proc.stdout)
            session_id = result.get("session_id", "?")
        except json.JSONDecodeError:
            pass

    log_event("claude", len(prompt), session_id, proc.returncode, duration)

    # Capture messages before possible early return or printing
    new_messages = read_new_messages(messages_log, prior_size)

    if proc.returncode != 0:
        print(f"[orchestrator] Claude exited with code {proc.returncode}",
              file=sys.stderr)
        if proc.stderr:
            print(f"[orchestrator] stderr: {proc.stderr[:500]}",
                  file=sys.stderr)
        write_session_log("claude", prompt, session_id, new_messages, duration, proc.returncode)
        return

    print(f"[orchestrator] Done. Session: {session_id}", file=sys.stderr)

    for msg in new_messages:
        print(f"Dot: {msg}")

    write_session_log("claude", prompt, session_id, new_messages, duration, proc.returncode)


def invoke_gemini(prompt: str) -> None:
    """Invoke Gemini CLI headlessly with the constructed prompt."""
    start_time = time.time()
    messages_log = HOME / "logs" / "messages.jsonl"
    prior_size = messages_log.stat().st_size if messages_log.exists() else 0

    cmd = [
        "gemini", "-p", prompt,
        "--allowed-mcp-server-names", "dot",
        "--output-format", "stream-json",
        "--approval-mode", "yolo",
    ]

    print(f"[orchestrator] Invoking gemini -p ({len(prompt)} chars)...",
          file=sys.stderr)

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(HOME),
    )
    
    duration = time.time() - start_time
    session_id = "?"
    
    if proc.stdout:
        for line in proc.stdout.splitlines():
            try:
                data = json.loads(line)
                if data.get("type") == "result":
                    session_id = data.get("session_id", "?")
                    break
            except json.JSONDecodeError:
                continue

    log_event("gemini", len(prompt), session_id, proc.returncode, duration)

    # Capture messages
    new_messages = read_new_messages(messages_log, prior_size)

    if proc.returncode != 0:
        print(f"[orchestrator] Gemini exited with code {proc.returncode}",
              file=sys.stderr)
        if proc.stderr:
            print(f"[orchestrator] stderr: {proc.stderr[:500]}",
                  file=sys.stderr)
        write_session_log("gemini", prompt, session_id, new_messages, duration, proc.returncode)
        return

    print(f"[orchestrator] Done. Session: {session_id}", file=sys.stderr)

    for msg in new_messages:
        print(f"Dot: {msg}")

    write_session_log("gemini", prompt, session_id, new_messages, duration, proc.returncode)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dot Orchestrator")
    parser.add_argument("event", nargs="?", default=None, help="The event to process")
    parser.add_argument("--harness", choices=["claude", "gemini"], default="claude", help="The AI harness to use")
    parser.add_argument("--tick-type", choices=["admin_message", "operational_check", "deep_reflection"], default="admin_message", help="The type of tick/event")
    parser.add_argument("--dry-run", action="store_true", help="Print the prompt and exit")
    
    args = parser.parse_args()
    
    # Backwards compatibility: if event is missing and it's an admin_message, use default perch text
    event = args.event
    if event is None:
        if args.tick_type == "admin_message":
            event = ""
        else:
            event = "" # Ignored by templates
            
    prompt = build_prompt(event, tick_type=args.tick_type)
    
    if args.dry_run:
        print(prompt)
        sys.exit(0)
    
    if args.harness == "gemini":
        invoke_gemini(prompt)
    else:
        invoke_claude(prompt)
