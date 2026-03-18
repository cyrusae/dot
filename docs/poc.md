# Proof of Concept: Claude Code CLI + MCP Tools for Dot

## Goal

Validate that Claude Code, invoked headlessly via `claude -p` with Pro subscription authentication, can autonomously complete a multi-step task using custom tools exposed through an MCP server. This is the single gating question for the hybrid open-strix/Claude Code architecture.

## What Success Looks Like

A single `claude -p` invocation that:
1. Reads memory blocks via an MCP tool
2. Performs work informed by those blocks
3. Sends a message via an MCP tool (simulated Discord output)
4. Writes a journal entry via an MCP tool
5. All without interactive prompts or permission approvals

If this works, the hybrid architecture is viable. If it doesn't, we need to understand why and whether it's a fixable configuration issue or a fundamental limitation.

## Prerequisites

### Install Claude Code
```bash
npm install -g @anthropic-ai/claude-code
```

### Authenticate with Pro Subscription
```bash
claude
# Select "Claude account with subscription" 
# Complete browser auth flow
# Verify with: claude -p "say hello" --output-format json
```

**Important**: If you have `ANTHROPIC_API_KEY` set in your environment, Claude Code will use that instead of your subscription. Unset it:
```bash
unset ANTHROPIC_API_KEY
```

### Install Python MCP Package
```bash
pip install mcp
```
Or with uv:
```bash
uv pip install mcp
```

### Create Working Directory
```bash
mkdir -p ~/dot-poc
cd ~/dot-poc
mkdir -p blocks logs
```

## Step 1: Seed Memory Blocks

Create two YAML files that will serve as the agent's hot memory context.

**`blocks/persona.yaml`**:
```yaml
name: persona
sort_order: 0
text: |
  You are Dot, a persistent AI agent in early development.
  You communicate with your human (Cyrus) via the send_message tool.
  You maintain your own memory by reading and writing blocks.
  You journal every interaction to maintain temporal awareness.
  Your final text output will be discarded — only tool calls matter.
```

**`blocks/current-focus.yaml`**:
```yaml
name: current-focus
sort_order: 10
text: |
  Current focus: This is a proof-of-concept test.
  Goal: Demonstrate that you can read blocks, send messages,
  and write journal entries autonomously.
  Status: First invocation — introduce yourself and confirm tools work.
```

## Step 2: Build the MCP Server

Create a single Python file that exposes four tools via the MCP stdio protocol. This server runs as a subprocess — Claude Code launches it and communicates via JSON-RPC over stdin/stdout.

**`dot_mcp_server.py`**:
```python
"""
Minimal MCP server exposing Dot's core tools for proof-of-concept.
Claude Code launches this as a subprocess via --mcp-config.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# The working directory where blocks/ and logs/ live.
# Set via environment variable so the MCP config can pass it in,
# or default to the current directory.
HOME_DIR = Path(os.environ.get("DOT_HOME", ".")).resolve()
BLOCKS_DIR = HOME_DIR / "blocks"
LOGS_DIR = HOME_DIR / "logs"

server = Server("dot-tools")


@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="send_message",
            description=(
                "Send a message to the human. This is your ONLY way to communicate. "
                "Your final text output is discarded — use this tool to speak."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The message text to send",
                    }
                },
                "required": ["text"],
            },
        ),
        Tool(
            name="read_block",
            description=(
                "Read a memory block by name. Returns the block's YAML content. "
                "Use list_blocks first if you don't know what blocks exist."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Block filename without extension (e.g. 'persona')",
                    }
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="write_block",
            description=(
                "Create or update a memory block. Writes a YAML file to blocks/. "
                "Use for persistent identity, operational state, and context."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Block name (becomes filename)",
                    },
                    "text": {
                        "type": "string",
                        "description": "Block content text",
                    },
                    "sort_order": {
                        "type": "integer",
                        "description": "Sort order for prompt injection (lower = earlier)",
                        "default": 0,
                    },
                },
                "required": ["name", "text"],
            },
        ),
        Tool(
            name="journal",
            description=(
                "Write a journal entry. Call this exactly once per interaction. "
                "Records what happened and your predictions about what comes next."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "user_wanted": {
                        "type": "string",
                        "description": "What the human wanted or what triggered this turn",
                    },
                    "agent_did": {
                        "type": "string",
                        "description": "What you actually did",
                    },
                    "predictions": {
                        "type": "string",
                        "description": "Your predictions about what will happen next",
                    },
                },
                "required": ["user_wanted", "agent_did", "predictions"],
            },
        ),
        Tool(
            name="list_blocks",
            description="List all available memory blocks with a short preview of each.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "send_message":
        return await handle_send_message(arguments)
    elif name == "read_block":
        return await handle_read_block(arguments)
    elif name == "write_block":
        return await handle_write_block(arguments)
    elif name == "journal":
        return await handle_journal(arguments)
    elif name == "list_blocks":
        return await handle_list_blocks(arguments)
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def handle_send_message(args: dict):
    text = args.get("text", "").strip()
    if not text:
        return [TextContent(type="text", text="Error: message text is empty")]

    # Log the message to a file (simulating Discord delivery)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOGS_DIR / "messages.jsonl"
    entry = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "type": "outbound_message",
        "text": text,
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    # Also print to stderr so you can see it in real-time
    print(f"[DOT → HUMAN] {text}", file=sys.stderr)

    return [TextContent(type="text", text=f"Message sent: {text[:80]}...")]


async def handle_read_block(args: dict):
    name = args.get("name", "").strip()
    if not name:
        return [TextContent(type="text", text="Error: block name is required")]

    path = BLOCKS_DIR / f"{name}.yaml"
    if not path.exists():
        return [TextContent(type="text", text=f"Block '{name}' not found")]

    content = path.read_text(encoding="utf-8")
    return [TextContent(type="text", text=content)]


async def handle_write_block(args: dict):
    import yaml

    name = args.get("name", "").strip()
    text = args.get("text", "")
    sort_order = args.get("sort_order", 0)

    if not name:
        return [TextContent(type="text", text="Error: block name is required")]

    BLOCKS_DIR.mkdir(parents=True, exist_ok=True)
    block = {"name": name, "sort_order": sort_order, "text": text}
    path = BLOCKS_DIR / f"{name}.yaml"
    path.write_text(
        yaml.safe_dump(block, sort_keys=False), encoding="utf-8"
    )

    return [TextContent(type="text", text=f"Block '{name}' written")]


async def handle_journal(args: dict):
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "user_wanted": args.get("user_wanted", ""),
        "agent_did": args.get("agent_did", ""),
        "predictions": args.get("predictions", ""),
    }
    log_path = LOGS_DIR / "journal.jsonl"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    return [TextContent(type="text", text="Journal entry recorded.")]


async def handle_list_blocks(args: dict):
    if not BLOCKS_DIR.exists():
        return [TextContent(type="text", text="No blocks directory found")]

    blocks = []
    for path in sorted(BLOCKS_DIR.glob("*.yaml")):
        try:
            import yaml
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            name = loaded.get("name", path.stem)
            text_preview = str(loaded.get("text", ""))[:80]
            blocks.append(f"- {name}: {text_preview}")
        except Exception:
            blocks.append(f"- {path.stem}: (error reading)")

    if not blocks:
        return [TextContent(type="text", text="No blocks found")]

    return [TextContent(type="text", text="\n".join(blocks))]


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

**Dependencies**: `pip install mcp pyyaml` (or `uv add mcp pyyaml`)

## Step 3: MCP Configuration

Create the config file that tells Claude Code how to launch your MCP server.

**`mcp-config.json`**:
```json
{
  "mcpServers": {
    "dot": {
      "command": "python3",
      "args": ["dot_mcp_server.py"],
      "env": {
        "DOT_HOME": "."
      }
    }
  }
}
```

**Note**: Adjust `command` to `python` if that's your system's Python 3 binary. The `DOT_HOME` env var tells the MCP server where to find `blocks/` and `logs/`.

## Step 4: Test the MCP Server Standalone

Before involving Claude Code, verify the MCP server starts and responds:

```bash
# This should start without errors and wait for JSON-RPC input
python3 dot_mcp_server.py
# Press Ctrl+C to stop
```

If it errors on import, install missing deps. The server uses stdio transport, so it won't produce visible output on its own — it's waiting for a client.

## Step 5: First Invocation

Run Claude Code headlessly with your MCP server:

```bash
cd ~/dot-poc

claude -p \
  "You are Dot. Read your memory blocks to understand who you are and what you're doing. Then send a greeting message to your human and write a journal entry about this interaction." \
  --mcp-config ./mcp-config.json \
  --allowedTools "mcp__dot__*" \
  --output-format stream-json \
  --dangerously-skip-permissions
```

### What to Watch For

**Success indicators:**
- Claude Code starts, connects to your MCP server
- You see `[DOT → HUMAN]` messages on stderr (from send_message)
- `logs/messages.jsonl` contains the outbound message
- `logs/journal.jsonl` contains a journal entry
- The stream-json output shows tool_use and tool_result events

**Likely failure modes and fixes:**
- "Permission denied" or tool approval prompts → ensure `--dangerously-skip-permissions` is present and you've run the initial permission acceptance (`claude --dangerously-skip-permissions` once interactively)
- "MCP server failed to start" → check that `python3 dot_mcp_server.py` runs without errors standalone
- API key override → ensure `ANTHROPIC_API_KEY` is unset; subscription auth must be active
- Rate limit hit → you're out of subscription budget; wait for the window to reset
- Tools not found → check that `--allowedTools "mcp__dot__*"` matches the server name "dot" in your config

## Step 6: Inspect Results

```bash
# Check what Dot said
cat logs/messages.jsonl | python3 -m json.tool

# Check what Dot journaled
cat logs/journal.jsonl | python3 -m json.tool

# Check if blocks were modified
ls -la blocks/
```

## Step 7: Simulate the Open-Strix Prompt Pattern

If Step 5 works, the next test simulates what open-strix's `_render_prompt()` does — injecting block contents and journal history into the prompt itself, as context for the current turn.

**`invoke_dot.py`** (a minimal orchestrator):
```python
"""
Minimal orchestrator that constructs a prompt the way open-strix does
and invokes Claude Code headlessly.
"""

import json
import subprocess
import sys
from pathlib import Path

import yaml

HOME = Path(".")
BLOCKS_DIR = HOME / "blocks"
JOURNAL_LOG = HOME / "logs" / "journal.jsonl"


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
        "--mcp-config", "./mcp-config.json",
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
```

Run it:
```bash
python3 invoke_dot.py "Cyrus says: Hey Dot, how are you settling in?"
```

Then:
```bash
python3 invoke_dot.py "Perch time tick. Check your state and decide if there's anything to do."
```

This second invocation tests whether Dot reads its own previous journal entry and responds coherently — the minimal temporal continuity test.

## What This Validates

| Question | How We'll Know |
|----------|---------------|
| Can Claude Code use custom MCP tools headlessly? | Tools fire, logs appear |
| Does subscription auth work in -p mode? | No API key charges, runs within rate limits |
| Can the agent complete a multi-tool autonomous loop? | read_block → send_message → journal in one invocation |
| Can we inject context like open-strix does? | invoke_dot.py prompt construction works |
| What does latency look like? | Wall-clock time of invocations |
| Is the stream-json output parseable? | invoke_dot.py parses tool calls |

## What Comes After (If PoC Succeeds)

1. **Fork open-strix** — strip deepagents dependency, wire in Claude Code CLI invocation at the `_process_event()` seam
2. **Port tools to MCP** — convert open-strix's 15 LangChain tools to MCP tool definitions
3. **Discord integration** — lift open-strix's Discord bridge as-is (it's infrastructure, not inference)
4. **Scheduling** — lift open-strix's APScheduler + cron pattern
5. **Obsidian integration** — add vault tools via the existing sidecar spec
6. **Gemini CLI fallback** — test whether the same MCP server works with `gemini` CLI
7. **Memory architecture refinement** — implement the nine-block design as YAML files, potentially move to append-only SQLite later

## What Comes After (If PoC Fails)

Diagnose why. Likely failure categories:
- **MCP + headless mode incompatibility**: Check if there's a workaround or if the Agent SDK (TypeScript/Python library, not CLI) is needed instead
- **Subscription auth doesn't work in -p mode**: Consider whether API credits with aggressive budget limits are acceptable
- **Tool loop doesn't complete autonomously**: May need `--dangerously-skip-permissions` configuration or explicit tool allowlisting adjustments
- **Fundamental limitation**: Fall back to Option A (pure open-strix fork with deepagents, API credits) or revisit Letta

In any failure case, the investment is small (a few hours) and the learning is high.
