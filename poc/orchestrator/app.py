import asyncio
import os
import sys
from pathlib import Path

# Add poc/ parent to path so we can import invoke_dot
sys.path.insert(0, str(Path(__file__).parent.parent))

from invoke_dot import build_prompt, invoke_claude, invoke_gemini, read_new_messages
from .models import AgentEvent
from .discord_bridge import DiscordBridge
from .scheduler import DotScheduler
from .config import load_config

HOME = Path(__file__).parent.parent  # poc/
MESSAGES_LOG = HOME / "logs" / "messages.jsonl"


def _get_harness(event: AgentEvent, default: str) -> str:
    """Determine which harness to use for this event."""
    # 1. Event-level override (e.g. from scheduler job)
    if event.harness:
        return event.harness

    # 2. Check routing-state block (Dot's self-expressed preference)
    routing_state = _read_routing_state()
    if routing_state:
        return routing_state

    # 3. Config default
    return default


def _read_routing_state() -> str | None:
    """Read Dot's preferred harness from routing-state warm block, if set."""
    routing_block = HOME / "blocks" / "routing-state.yaml"
    if not routing_block.exists():
        return None
    try:
        import yaml
        data = yaml.safe_load(routing_block.read_text(encoding="utf-8"))
        text_field = data.get("text", "")
        if not text_field:
            return None
        
        parsed = yaml.safe_load(text_field)
        if not parsed:
            return None
            
        harness = parsed.get("preferred_harness")
        return harness if harness else None
    except Exception:
        return None


async def _event_worker(queue: asyncio.Queue, discord_bridge: DiscordBridge | None, default_harness: str):
    """Process events from the queue one at a time."""
    while True:
        event: AgentEvent = await queue.get()

        try:
            prior_size = MESSAGES_LOG.stat().st_size if MESSAGES_LOG.exists() else 0

            prompt = build_prompt(event.prompt, tick_type=event.tick_type)
            harness = _get_harness(event, default_harness)

            print(f"[coordinator] Processing {event.event_type} via {harness}", flush=True)

            # Run the blocking CLI invocation in a thread pool
            loop = asyncio.get_event_loop()
            if harness == "gemini":
                await loop.run_in_executor(None, invoke_gemini, prompt)
            else:
                await loop.run_in_executor(None, invoke_claude, prompt)

            # Route new messages.jsonl entries to Discord if we have a channel
            if discord_bridge and event.channel_id:
                new_messages = read_new_messages(MESSAGES_LOG, prior_size)
                for msg in new_messages:
                    await discord_bridge.send_to_discord(event.channel_id, msg)

        except Exception as e:
            print(f"[coordinator] Error processing event: {e}", flush=True)

        finally:
            queue.task_done()


async def run(config_path: Path | None = None):
    """Main async entry point for the coordinator."""
    if config_path is None:
        config_path = HOME / "config.yaml"

    if not config_path.exists():
        print(f"[coordinator] Config not found: {config_path}")
        sys.exit(1)

    config = load_config(config_path)

    queue: asyncio.Queue = asyncio.Queue()

    # Start scheduler
    scheduler = None
    if config.get("scheduler", {}).get("enabled", True):
        scheduler_yaml = HOME / config.get("scheduler", {}).get("yaml_path", "scheduler.yaml")
        scheduler = DotScheduler(scheduler_yaml, queue)
        scheduler.start()
        print("[coordinator] Scheduler started")

    # Start Discord bridge (only if token is available)
    discord_bridge = None
    discord_token = config.get("discord", {}).get("token", "")
    if discord_token:
        discord_config = config.get("discord", {})
        discord_bridge = DiscordBridge(discord_config, queue)
        # Run discord client in background task
        asyncio.create_task(discord_bridge.start(discord_token))
        print("[coordinator] Discord bridge starting...")
    else:
        print("[coordinator] No DISCORD_TOKEN set — Discord bridge disabled")

    default_harness = config.get("harness", {}).get("default", "claude")

    # Run event worker
    await _event_worker(queue, discord_bridge, default_harness)


def main():
    """Entry point for `dot-coordinator` CLI command."""
    import argparse
    parser = argparse.ArgumentParser(description="Dot Coordinator")
    parser.add_argument("--config", type=Path, default=None, help="Path to config.yaml")
    args = parser.parse_args()

    asyncio.run(run(args.config))


if __name__ == "__main__":
    main()
