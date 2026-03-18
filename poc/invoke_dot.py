"""
Minimal orchestrator that constructs a prompt the way open-strix does
and invokes Claude Code headlessly.
"""

import json
import subprocess
import sys
from pathlib import Path

import yaml

HOME = Path(__file__).parent
BLOCKS_DIR = HOME / "blocks"
JOURNAL_LOG = HOME / "logs" / "journal.jsonl"
MCP_CONFIG = HOME / "mcp-config.json"
SERVER_SCRIPT = HOME / "dot_mcp_server.py"


def load_blocks() -> str:
    """Load all memory blocks, sorted by sort_order."""
    blocks = []
    for path in sorted(BLOCKS_DIR.glob("*.yaml")):
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            name = loaded.get("name", path.stem)
            text = loaded.get("text", "")
            sort_order = loaded.get("sort_order", 0)
            blocks.append((sort_order, name, text))
        except Exception:
            continue

    blocks.sort(key=lambda b: (b[0], b[1]))
    rendered = []
    for _, name, text in blocks:
        rendered.append(f"memory block: {name}\n{text}")
    return "\n\n".join(rendered) if rendered else "(no blocks)"


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


def build_prompt(current_event: str) -> str:
    """Build the full turn prompt with context injection."""
    blocks = load_blocks()
    journal = load_journal()

    return f"""Context for this turn:

1) Last journal entries:
{journal}

2) Memory blocks:
{blocks}

3) Current event:
{current_event}

Remember: Use send_message to communicate. Your final text output is discarded.
Call journal exactly once at the end of your turn.
"""


def invoke_claude(prompt: str) -> None:
    """Invoke Claude Code headlessly with the constructed prompt."""
    cmd = [
        "claude", "-p", prompt,
        "--mcp-config", str(MCP_CONFIG),
        "--allowedTools", "mcp__dot__*",
        "--output-format", "stream-json",
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

    if proc.returncode != 0:
        print(f"[orchestrator] Claude exited with code {proc.returncode}",
              file=sys.stderr)
        if proc.stderr:
            print(f"[orchestrator] stderr: {proc.stderr[:500]}",
                  file=sys.stderr)

    # Parse stream-json output for tool calls
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
            event_type = event.get("type", "")
            if event_type == "tool_use":
                tool_name = event.get("tool", {}).get("name", "?")
                print(f"[orchestrator] Tool call: {tool_name}",
                      file=sys.stderr)
            elif event_type == "result":
                print(f"[orchestrator] Done. Session: {event.get('session_id', '?')}",
                      file=sys.stderr)
        except json.JSONDecodeError:
            continue


if __name__ == "__main__":
    event = sys.argv[1] if len(sys.argv) > 1 else "Perch time tick. Check your state and do something useful."
    prompt = build_prompt(event)
    invoke_claude(prompt)
