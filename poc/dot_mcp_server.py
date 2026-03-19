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
VAULT_DIR = HOME_DIR / "vault"

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
                    "tier": {
                        "type": "string",
                        "enum": ["hot", "warm"],
                        "description": "Storage tier (hot = auto-loaded, warm = on-demand)",
                        "default": "hot",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Metadata tags for warm block discovery",
                        "default": [],
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
                    "user_wanted": {"type": "string", "description": "What the human wanted or what triggered this turn"},
                    "agent_did": {"type": "string", "description": "What you actually did"},
                    "predictions": {"type": "string", "description": "Your predictions about what will happen next"},
                },
                "required": ["user_wanted", "agent_did", "predictions"],
            },
        ),
        Tool(
            name="list_blocks",
            description="List all available memory blocks grouped by tier (HOT/WARM) with metadata and previews.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="vault_read",
            description="Read a note from the vault. Returns frontmatter and body separately.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to vault root (e.g. 'research/note.md')"},
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="vault_write",
            description="Write a note to the vault. Requires overwrite=True to replace existing files.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to vault root"},
                    "content": {"type": "string", "description": "Markdown content (can include frontmatter)"},
                    "overwrite": {"type": "boolean", "description": "Must be True to overwrite", "default": False},
                },
                "required": ["path", "content"],
            },
        ),
        Tool(
            name="vault_append",
            description="Append content to an existing vault note.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to vault root"},
                    "content": {"type": "string", "description": "Content to append"},
                },
                "required": ["path", "content"],
            },
        ),
        Tool(
            name="vault_delete",
            description="Delete a note from the vault.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to vault root"},
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="vault_rename",
            description="Move or rename a vault note.",
            inputSchema={
                "type": "object",
                "properties": {
                    "old_path": {"type": "string", "description": "Current path"},
                    "new_path": {"type": "string", "description": "New path"},
                },
                "required": ["old_path", "new_path"],
            },
        ),
        Tool(
            name="vault_search",
            description="Search vault contents using ripgrep with optional metadata filters.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "type_filter": {"type": "string", "description": "Filter by 'type' frontmatter"},
                    "tag_filter": {"type": "string", "description": "Filter by 'tags' frontmatter"},
                    "status_filter": {"type": "string", "description": "Filter by 'status' frontmatter"},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="vault_backlinks",
            description="Find all notes linking to a given note via [[wikilinks]].",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path of the target note"},
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="vault_list",
            description="List markdown files in the vault as a tree-style listing.",
            inputSchema={
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Subdirectory to list", "default": ""},
                },
            },
        ),
        Tool(
            name="vault_stats",
            description="Get vault statistics (note counts by type and status).",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="vault_related",
            description="Find notes sharing tags or related_interests with the given note.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path of the reference note"},
                    "limit": {"type": "integer", "description": "Max results", "default": 5},
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="read_inbox",
            description="Read messages sent to Dot from the inbox queue (logs/inbox.jsonl). Call this at the start of turns when you expect input from Cyrus.",
            inputSchema={
                "type": "object",
                "properties": {
                    "clear": {
                        "type": "boolean",
                        "description": "Mark messages as read after returning them",
                        "default": False,
                    }
                },
            },
        ),
        Tool(
            name="schedule_job",
            description="Schedule a recurring job by writing to scheduler.yaml. Replaces existing job with the same name.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Unique name for the job"},
                    "trigger": {"type": "string", "enum": ["interval", "cron"], "description": "Trigger type"},
                    "tick_type": {
                        "type": "string",
                        "enum": ["admin_message", "operational_check", "deep_reflection"],
                        "description": "Type of tick to emit"
                    },
                    "prompt": {"type": "string", "description": "Optional prompt text to include in the event", "default": ""},
                    "harness": {"type": "string", "description": "Optional harness override (claude|gemini)", "default": None},
                    "hours": {"type": "integer", "description": "Interval hours", "default": 0},
                    "minutes": {"type": "integer", "description": "Interval minutes", "default": 0},
                    "seconds": {"type": "integer", "description": "Interval seconds", "default": 0},
                    "cron": {"type": "string", "description": "Cron expression (min hour day month dow)", "default": ""},
                },
                "required": ["name", "trigger", "tick_type"],
            },
        ),
        Tool(
            name="unschedule_job",
            description="Remove a scheduled job by name from scheduler.yaml.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the job to remove"},
                },
                "required": ["name"],
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
    elif name == "read_inbox":
        return await handle_read_inbox(arguments)
    elif name == "schedule_job":
        return await handle_schedule_job(arguments)
    elif name == "unschedule_job":
        return await handle_unschedule_job(arguments)
    elif name.startswith("vault_"):
        handler_name = f"handle_{name}"
        handler = globals().get(handler_name)
        if handler:
            return await handler(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown vault tool: {name}")]
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


def _git_commit_block(name: str, block_path: Path):
    import subprocess
    repo_root = block_path.parent.parent
    try:
        # git -C {block_path.parent.parent} add {block_path}
        subprocess.run(
            ["git", "-C", str(repo_root), "add", str(block_path)],
            capture_output=True,
            text=True
        )
        # git -C {block_path.parent.parent} commit -m 'block: update {name}'
        subprocess.run(
            ["git", "-C", str(repo_root), "commit", "-m", f"block: update {name}"],
            capture_output=True,
            text=True
        )
    except Exception as e:
        print(f"Git commit failed for block '{name}': {e}", file=sys.stderr)


async def handle_write_block(args: dict):
    import yaml

    name = args.get("name", "").strip()
    text = args.get("text", "")
    tier = args.get("tier", "hot")
    tags = args.get("tags", [])
    sort_order = args.get("sort_order", 0)

    if not name:
        return [TextContent(type="text", text="Error: block name is required")]

    BLOCKS_DIR.mkdir(parents=True, exist_ok=True)
    block = {
        "name": name,
        "tier": tier,
        "tags": tags,
        "sort_order": sort_order,
        "text": text
    }
    path = BLOCKS_DIR / f"{name}.yaml"
    path.write_text(yaml.safe_dump(block, sort_keys=False), encoding="utf-8")

    _git_commit_block(name, path)

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

    import yaml
    hot_blocks = []
    warm_blocks = []

    for path in sorted(BLOCKS_DIR.glob("*.yaml")):
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            name = loaded.get("name", path.stem)
            tier = loaded.get("tier", "hot")
            tags = loaded.get("tags", [])
            sort_order = loaded.get("sort_order", 0)
            text_preview = str(loaded.get("text", "")).strip().replace("\n", " ")[:60]

            if tier == "warm":
                tags_str = f" [{', '.join(tags)}]" if tags else ""
                warm_blocks.append((sort_order, f"  {name} [{sort_order}]{tags_str}: {text_preview}"))
            else:
                hot_blocks.append((sort_order, f"  {name} [{sort_order}]: {text_preview}"))
        except Exception as e:
            hot_blocks.append((999, f"  {path.stem}: (error reading: {e})"))

    # Sort by sort_order
    hot_blocks.sort(key=lambda x: x[0])
    warm_blocks.sort(key=lambda x: x[0])

    output = []
    if hot_blocks:
        output.append("HOT (auto-loaded):")
        output.extend([b[1] for b in hot_blocks])

    if warm_blocks:
        if output:
            output.append("")
        output.append("WARM (read via read_block):")
        output.extend([b[1] for b in warm_blocks])

    if not output:
        return [TextContent(type="text", text="No blocks found")]

    return [TextContent(type="text", text="\n".join(output))]


# --- Vault Tools ---

def _parse_vault_note(content: str):
    import yaml
    import re

    frontmatter = {}
    body = content
    if content.startswith("---"):
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", content, re.DOTALL)
        if match:
            try:
                frontmatter = yaml.safe_load(match.group(1)) or {}
                body = match.group(2)
            except Exception:
                pass
    return frontmatter, body


async def handle_vault_read(args: dict):
    path_str = args.get("path", "").strip()
    if not path_str:
        return [TextContent(type="text", text="Error: path is required")]

    path = VAULT_DIR / path_str
    if not path.exists():
        return [TextContent(type="text", text=f"Error: file not found: {path_str}")]

    content = path.read_text(encoding="utf-8")
    frontmatter, body = _parse_vault_note(content)

    res = {
        "path": path_str,
        "frontmatter": frontmatter,
        "body": body,
        "backend": "filesystem"
    }
    return [TextContent(type="text", text=json.dumps(res, indent=2))]


async def handle_vault_write(args: dict):
    import yaml
    path_str = args.get("path", "").strip()
    content = args.get("content", "")
    overwrite = args.get("overwrite", False)

    if not path_str:
        return [TextContent(type="text", text="Error: path is required")]

    path = VAULT_DIR / path_str
    if path.exists() and not overwrite:
        return [TextContent(type="text", text="Error: File exists; pass overwrite=true to replace")]

    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    path.parent.mkdir(parents=True, exist_ok=True)

    # If content already has frontmatter, parse it and update dates
    frontmatter, body = _parse_vault_note(content)
    today = datetime.now().strftime("%Y-%m-%d")

    if "created" not in frontmatter:
        frontmatter["created"] = today
    frontmatter["modified"] = today

    full_content = "---\n" + yaml.safe_dump(frontmatter, sort_keys=False).strip() + "\n---\n\n" + body.strip()
    path.write_text(full_content, encoding="utf-8")

    return [TextContent(type="text", text=json.dumps({"path": path_str, "status": "written", "backend": "filesystem"}))]


async def handle_vault_append(args: dict):
    path_str = args.get("path", "").strip()
    content_to_append = args.get("content", "")

    if not path_str:
        return [TextContent(type="text", text="Error: path is required")]

    path = VAULT_DIR / path_str
    if not path.exists():
        return [TextContent(type="text", text=f"Error: file not found: {path_str}")]

    existing_content = path.read_text(encoding="utf-8")
    frontmatter, body = _parse_vault_note(existing_content)

    today = datetime.now().strftime("%Y-%m-%d")
    frontmatter["modified"] = today

    import yaml
    new_body = body.rstrip() + "\n\n" + content_to_append.strip()
    full_content = "---\n" + yaml.safe_dump(frontmatter, sort_keys=False).strip() + "\n---\n\n" + new_body
    path.write_text(full_content, encoding="utf-8")

    return [TextContent(type="text", text=json.dumps({"path": path_str, "status": "appended", "backend": "filesystem"}))]


async def handle_vault_delete(args: dict):
    path_str = args.get("path", "").strip()
    if not path_str:
        return [TextContent(type="text", text="Error: path is required")]

    path = VAULT_DIR / path_str
    if not path.exists():
        return [TextContent(type="text", text=f"Error: file not found: {path_str}")]

    path.unlink()
    return [TextContent(type="text", text=json.dumps({"path": path_str, "status": "deleted", "backend": "filesystem"}))]


async def handle_vault_rename(args: dict):
    old_path_str = args.get("old_path", "").strip()
    new_path_str = args.get("new_path", "").strip()

    if not old_path_str or not new_path_str:
        return [TextContent(type="text", text="Error: both old_path and new_path are required")]

    old_path = VAULT_DIR / old_path_str
    new_path = VAULT_DIR / new_path_str

    if not old_path.exists():
        return [TextContent(type="text", text=f"Error: file not found: {old_path_str}")]

    new_path.parent.mkdir(parents=True, exist_ok=True)
    old_path.rename(new_path)

    return [TextContent(type="text", text=json.dumps({
        "old_path": old_path_str,
        "new_path": new_path_str,
        "status": "renamed",
        "note": "Backlinks not updated without Obsidian sidecar",
        "backend": "filesystem"
    }))]


async def handle_vault_search(args: dict):
    import subprocess
    query = args.get("query", "")
    type_filter = args.get("type_filter")
    tag_filter = args.get("tag_filter")
    status_filter = args.get("status_filter")

    if not VAULT_DIR.exists():
        return [TextContent(type="text", text=json.dumps({"results": [], "backend": "filesystem"}))]

    results = []
    # Try ripgrep first
    try:
        cmd = ["rg", "-l", query, str(VAULT_DIR)]
        output = subprocess.check_output(cmd, text=True).splitlines()
        candidate_paths = [Path(p) for p in output]
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback to glob + string search
        candidate_paths = []
        for p in VAULT_DIR.rglob("*.md"):
            try:
                if query.lower() in p.read_text(encoding="utf-8").lower():
                    candidate_paths.append(p)
            except Exception:
                continue

    for p in candidate_paths:
        try:
            content = p.read_text(encoding="utf-8")
            frontmatter, _ = _parse_vault_note(content)

            if type_filter and frontmatter.get("type") != type_filter:
                continue
            if tag_filter:
                tags = frontmatter.get("tags", [])
                if isinstance(tags, str): tags = [tags]
                if tag_filter not in tags:
                    continue
            if status_filter and frontmatter.get("status") != status_filter:
                continue

            rel_path = str(p.relative_to(VAULT_DIR))
            results.append(rel_path)
        except Exception:
            continue

    return [TextContent(type="text", text=json.dumps({"results": results, "backend": "filesystem"}))]


async def handle_vault_backlinks(args: dict):
    import subprocess
    import re
    path_str = args.get("path", "").strip()
    if not path_str:
        return [TextContent(type="text", text="Error: path is required")]

    # Get stem for [[wikilink]] search
    stem = Path(path_str).stem
    pattern = f"\\[\\[{re.escape(stem)}(\\|.*)?\\]\\]"

    results = []
    if not VAULT_DIR.exists():
        return [TextContent(type="text", text=json.dumps({"backlinks": [], "backend": "filesystem"}))]

    try:
        cmd = ["rg", "-l", pattern, str(VAULT_DIR)]
        output = subprocess.check_output(cmd, text=True).splitlines()
        results = [str(Path(p).relative_to(VAULT_DIR)) for p in output]
    except (subprocess.CalledProcessError, FileNotFoundError):
        for p in VAULT_DIR.rglob("*.md"):
            try:
                if re.search(pattern, p.read_text(encoding="utf-8")):
                    results.append(str(p.relative_to(VAULT_DIR)))
            except Exception:
                continue

    # Exclude the file itself
    results = [r for r in results if r != path_str]

    return [TextContent(type="text", text=json.dumps({"backlinks": results, "backend": "filesystem"}))]


async def handle_vault_list(args: dict):
    directory = args.get("directory", "").strip()
    target_dir = VAULT_DIR / directory

    if not target_dir.exists():
        return [TextContent(type="text", text=f"Error: directory not found: {directory}")]

    def build_tree(path, rel_root):
        tree = []
        for p in sorted(path.iterdir()):
            if p.name.startswith("."): continue
            if p.is_dir():
                subtree = build_tree(p, rel_root)
                if subtree:
                    tree.append(f"📁 {p.name}/")
                    tree.extend([f"  {line}" for line in subtree])
            elif p.suffix == ".md":
                tree.append(f"📄 {p.name}")
        return tree

    tree = build_tree(target_dir, target_dir)
    return [TextContent(type="text", text="\n".join(tree) or "(empty)")]


_stats_cache = {"time": 0, "data": None}

async def handle_vault_stats(args: dict):
    import time
    now = time.time()
    if _stats_cache["data"] and (now - _stats_cache["time"] < 300):
        return [TextContent(type="text", text=json.dumps(_stats_cache["data"], indent=2))]

    if not VAULT_DIR.exists():
        return [TextContent(type="text", text=json.dumps({"total_notes": 0, "backend": "filesystem"}))]

    stats = {
        "total_notes": 0,
        "by_type": {},
        "by_status": {},
        "backend": "filesystem"
    }

    for p in VAULT_DIR.rglob("*.md"):
        stats["total_notes"] += 1
        try:
            frontmatter, _ = _parse_vault_note(p.read_text(encoding="utf-8"))
            ntype = frontmatter.get("type", "unknown")
            stats["by_type"][ntype] = stats["by_type"].get(ntype, 0) + 1
            status = frontmatter.get("status", "unknown")
            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
        except Exception:
            continue

    _stats_cache["time"] = now
    _stats_cache["data"] = stats
    return [TextContent(type="text", text=json.dumps(stats, indent=2))]


async def handle_vault_related(args: dict):
    path_str = args.get("path", "").strip()
    limit = args.get("limit", 5)

    if not path_str:
        return [TextContent(type="text", text="Error: path is required")]

    ref_path = VAULT_DIR / path_str
    if not ref_path.exists():
        return [TextContent(type="text", text=f"Error: file not found: {path_str}")]

    ref_fm, _ = _parse_vault_note(ref_path.read_text(encoding="utf-8"))
    ref_tags = set(ref_fm.get("tags", []))
    if isinstance(ref_fm.get("tags"), str): ref_tags = {ref_fm["tags"]}
    ref_interests = set(ref_fm.get("related_interests", []))

    scores = []
    for p in VAULT_DIR.rglob("*.md"):
        if p == ref_path: continue
        try:
            fm, _ = _parse_vault_note(p.read_text(encoding="utf-8"))
            tags = set(fm.get("tags", []))
            if isinstance(fm.get("tags"), str): tags = {fm["tags"]}
            interests = set(fm.get("related_interests", []))

            score = len(ref_tags & tags) + (len(ref_interests & interests) * 2)
            if score > 0:
                scores.append({
                    "path": str(p.relative_to(VAULT_DIR)),
                    "score": score,
                    "matched_tags": list(ref_tags & tags),
                    "matched_interests": list(ref_interests & interests)
                })
        except Exception:
            continue

    scores.sort(key=lambda x: x["score"], reverse=True)
    return [TextContent(type="text", text=json.dumps({
        "related": scores[:limit],
        "backend": "filesystem"
    }, indent=2))]


async def handle_read_inbox(args: dict):
    clear = args.get("clear", False)
    inbox_path = LOGS_DIR / "inbox.jsonl"

    if not inbox_path.exists():
        return [TextContent(type="text", text="Inbox is empty.")]

    messages = []
    unread_messages = []

    try:
        with inbox_path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    msg = json.loads(line)
                    messages.append(msg)
                    if not msg.get("read", False):
                        unread_messages.append(msg)
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        return [TextContent(type="text", text=f"Error reading inbox: {e}")]

    if not unread_messages:
        return [TextContent(type="text", text="No unread messages.")]

    formatted = []
    for msg in unread_messages:
        ts = msg.get("timestamp", "unknown")
        sender = msg.get("from", "unknown")
        text = msg.get("text", "")
        formatted.append(f"[{ts}] from {sender}: {text}")

    result_text = "\n".join(formatted)

    if clear:
        # Rewrite the file with marked messages
        for msg in messages:
            if not msg.get("read", False):
                msg["read"] = True
        try:
            with inbox_path.open("w", encoding="utf-8") as f:
                for msg in messages:
                    f.write(json.dumps(msg) + "\n")
        except Exception as e:
            result_text += f"\n\n(Note: Failed to mark as read: {e})"

    return [TextContent(type="text", text=result_text)]


async def handle_schedule_job(args: dict):
    import yaml
    name = args.get("name")
    trigger = args.get("trigger")
    tick_type = args.get("tick_type")
    prompt = args.get("prompt", "")
    harness = args.get("harness")
    hours = args.get("hours", 0)
    minutes = args.get("minutes", 0)
    seconds = args.get("seconds", 0)
    cron = args.get("cron", "")

    if not name or not trigger or not tick_type:
        return [TextContent(type="text", text="Error: name, trigger, and tick_type are required")]

    scheduler_path = HOME_DIR / "scheduler.yaml"
    if scheduler_path.exists():
        try:
            data = yaml.safe_load(scheduler_path.read_text(encoding="utf-8")) or {}
        except Exception as e:
            return [TextContent(type="text", text=f"Error reading scheduler.yaml: {e}")]
    else:
        data = {"jobs": []}

    if "jobs" not in data or not isinstance(data["jobs"], list):
        data["jobs"] = []

    new_job = {
        "name": name,
        "trigger": trigger,
        "tick_type": tick_type,
        "prompt": prompt,
    }
    if harness:
        new_job["harness"] = harness
    if trigger == "interval":
        new_job["hours"] = hours
        new_job["minutes"] = minutes
        new_job["seconds"] = seconds
    elif trigger == "cron":
        new_job["cron"] = cron

    # Replace existing job or append
    updated = False
    for i, job in enumerate(data["jobs"]):
        if job.get("name") == name:
            data["jobs"][i] = new_job
            updated = True
            break
    
    if not updated:
        data["jobs"].append(new_job)

    try:
        scheduler_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    except Exception as e:
        return [TextContent(type="text", text=f"Error writing scheduler.yaml: {e}")]

    return [TextContent(type="text", text=f"Job '{name}' scheduled successfully.")]


async def handle_unschedule_job(args: dict):
    import yaml
    name = args.get("name")
    if not name:
        return [TextContent(type="text", text="Error: name is required")]

    scheduler_path = HOME_DIR / "scheduler.yaml"
    if not scheduler_path.exists():
        return [TextContent(type="text", text="Error: scheduler.yaml not found")]

    try:
        data = yaml.safe_load(scheduler_path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        return [TextContent(type="text", text=f"Error reading scheduler.yaml: {e}")]

    if "jobs" not in data or not isinstance(data["jobs"], list):
        return [TextContent(type="text", text=f"Job '{name}' not found")]

    original_count = len(data["jobs"])
    data["jobs"] = [job for job in data["jobs"] if job.get("name") != name]

    if len(data["jobs"]) == original_count:
        return [TextContent(type="text", text=f"Job '{name}' not found")]

    try:
        scheduler_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    except Exception as e:
        return [TextContent(type="text", text=f"Error writing scheduler.yaml: {e}")]

    return [TextContent(type="text", text=f"Job '{name}' unscheduled successfully.")]


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
