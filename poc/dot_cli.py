"""
dot — CLI entry point for the Dot agent system.

Usage:
    dot say "message"                  # send a message to Dot (claude)
    dot say "message" --harness gemini # send via gemini
    dot tick                           # operational_check tick
    dot reflect                        # deep_reflection tick
    dot dry-run "message"              # print prompt, don't invoke
    dot dry-run --tick-type operational_check

    dot inbox add "message"            # append to inbox
    dot inbox show                     # show unread messages
    dot inbox clear                    # mark all as read

    dot log show [--count N]           # last N journal entries
    dot log events [--count N]         # last N event log entries
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

HOME = Path(__file__).parent

from invoke_dot import (
    build_prompt,
    invoke_claude,
    invoke_gemini,
    load_inbox,
    load_journal,
    EVENT_LOG,
    JOURNAL_LOG,
)


# ── Inbox helpers ──────────────────────────────────────────────

INBOX_LOG = HOME / "logs" / "inbox.jsonl"


def inbox_add(text: str) -> None:
    INBOX_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "from": "Cyrus",
        "text": text,
        "read": False,
        "conversation_id": "cli",
    }
    with open(INBOX_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"Added to inbox: {text}")


def inbox_show() -> None:
    content = load_inbox()
    if content:
        print(content)
    else:
        print("No unread messages.")


def inbox_clear() -> None:
    if not INBOX_LOG.exists():
        print("Inbox is empty.")
        return

    lines = INBOX_LOG.read_text(encoding="utf-8").splitlines()
    updated = []
    count = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            if not entry.get("read"):
                count += 1
            entry["read"] = True
            updated.append(json.dumps(entry))
        except json.JSONDecodeError:
            updated.append(line)

    INBOX_LOG.write_text("\n".join(updated) + "\n", encoding="utf-8")
    print(f"Marked {count} message(s) as read.")


# ── Log helpers ────────────────────────────────────────────────

def log_show(count: int = 10) -> None:
    print(load_journal(count))


def log_events(count: int = 10) -> None:
    if not EVENT_LOG.exists():
        print("(no events)")
        return

    entries = []
    for line in EVENT_LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    for entry in entries[-count:]:
        ts = entry.get("timestamp", "?")
        harness = entry.get("harness", "?")
        rc = entry.get("return_code", "?")
        dur = entry.get("duration_seconds", "?")
        chars = entry.get("prompt_chars", "?")
        print(f"[{ts}] harness={harness} rc={rc} duration={dur}s prompt={chars}ch")


# ── CLI definition ─────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dot", description="Dot agent CLI")
    sub = parser.add_subparsers(dest="command")

    # dot say
    p_say = sub.add_parser("say", help="Send a message to Dot")
    p_say.add_argument("message", nargs="?", default=None, help="Message text")
    p_say.add_argument("--harness", choices=["claude", "gemini"], default="claude")

    # dot tick
    sub.add_parser("tick", help="Operational check tick")

    # dot reflect
    sub.add_parser("reflect", help="Deep reflection tick")

    # dot dry-run
    p_dry = sub.add_parser("dry-run", help="Print prompt without invoking")
    p_dry.add_argument("message", nargs="?", default=None, help="Message text")
    p_dry.add_argument(
        "--tick-type",
        choices=["admin_message", "operational_check", "deep_reflection"],
        default="admin_message",
    )

    # dot inbox
    p_inbox = sub.add_parser("inbox", help="Manage inbox")
    inbox_sub = p_inbox.add_subparsers(dest="inbox_command")
    p_inbox_add = inbox_sub.add_parser("add", help="Add a message to inbox")
    p_inbox_add.add_argument("message", help="Message text")
    inbox_sub.add_parser("show", help="Show unread messages")
    inbox_sub.add_parser("clear", help="Mark all messages as read")

    # dot log
    p_log = sub.add_parser("log", help="View logs")
    log_sub = p_log.add_subparsers(dest="log_command")
    p_log_show = log_sub.add_parser("show", help="Show journal entries")
    p_log_show.add_argument("--count", type=int, default=10)
    p_log_events = log_sub.add_parser("events", help="Show event log")
    p_log_events.add_argument("--count", type=int, default=10)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    # ── say ──
    if args.command == "say":
        if not args.message:
            print("Usage: dot say \"message\"", file=sys.stderr)
            sys.exit(1)

        # Write conversation context for skills to read
        turn_state_path = HOME / "logs" / ".turn_state.json"
        turn_state_path.parent.mkdir(parents=True, exist_ok=True)
        turn_state = {
            "count": 0, 
            "messages": [], 
            "conversation_id": "cli", 
            "author": "Cyrus", 
            "author_id": "cli:cyrus", 
            "platform": "cli"
        }
        turn_state_path.write_text(json.dumps(turn_state), encoding="utf-8")

        prompt = build_prompt(
            args.message, 
            tick_type="admin_message",
            conversation_id="cli",
            author="Cyrus",
            author_id="cli:cyrus"
        )
        if args.harness == "gemini":
            invoke_gemini(prompt)
        else:
            invoke_claude(prompt)

    # ── tick ──
    elif args.command == "tick":
        # Write context
        turn_state_path = HOME / "logs" / ".turn_state.json"
        turn_state_path.parent.mkdir(parents=True, exist_ok=True)
        turn_state = {
            "count": 0, 
            "messages": [], 
            "conversation_id": "cli", 
            "author": "Cyrus", 
            "author_id": "cli:cyrus", 
            "platform": "cli"
        }
        turn_state_path.write_text(json.dumps(turn_state), encoding="utf-8")

        prompt = build_prompt("", tick_type="operational_check", conversation_id="cli")
        invoke_claude(prompt)

    # ── reflect ──
    elif args.command == "reflect":
        # Write context
        turn_state_path = HOME / "logs" / ".turn_state.json"
        turn_state_path.parent.mkdir(parents=True, exist_ok=True)
        turn_state = {
            "count": 0, 
            "messages": [], 
            "conversation_id": "cli", 
            "author": "Cyrus", 
            "author_id": "cli:cyrus", 
            "platform": "cli"
        }
        turn_state_path.write_text(json.dumps(turn_state), encoding="utf-8")

        prompt = build_prompt("", tick_type="deep_reflection", conversation_id="cli")
        invoke_claude(prompt)

    # ── dry-run ──
    elif args.command == "dry-run":
        event = args.message or ""
        prompt = build_prompt(event, tick_type=args.tick_type, conversation_id="cli")
        print(prompt)

    # ── inbox ──
    elif args.command == "inbox":
        if args.inbox_command == "add":
            inbox_add(args.message)
        elif args.inbox_command == "show":
            inbox_show()
        elif args.inbox_command == "clear":
            inbox_clear()
        else:
            print("Usage: dot inbox {add,show,clear}", file=sys.stderr)
            sys.exit(1)

    # ── log ──
    elif args.command == "log":
        if args.log_command == "show":
            log_show(args.count)
        elif args.log_command == "events":
            log_events(args.count)
        else:
            print("Usage: dot log {show,events}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
