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
                    "name": {"type": "string", "description": "Block name (becomes filename)"},
                    "text": {"type": "string", "description": "Block content text"},
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
                    "user_wanted": {"type": "string", "description": "What the human wanted or what triggered this turn"},
                    "agent_did": {"type": "string", "description": "What you actually did"},
                    "predictions": {"type": "string", "description": "Your predictions about what will happen next"},
                },
                "required": ["user_wanted", "agent_did", "predictions"],
            },
        ),
        Tool(
            name="list_blocks",
            description="List all available memory blocks with a short preview of each.",
            inputSchema={"type": "object", "properties": {}},
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

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOGS_DIR / "messages.jsonl"
    entry = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "type": "outbound_message",
        "text": text,
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    print(f"[DOT → HUMAN] {text}", file=sys.stderr)

    # Don't truncate — return the full confirmation
    return [TextContent(type="text", text=f"Message sent ({len(text)} chars).")]


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
    path.write_text(yaml.safe_dump(block, sort_keys=False), encoding="utf-8")

    return [TextContent(type="text", text=f"Block '{name}' written.")]


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
