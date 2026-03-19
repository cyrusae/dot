from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentEvent:
    event_type: str  # "discord_message", "scheduler_tick", "admin_message"
    prompt: str      # the event text/message content
    channel_id: Optional[int] = None
    channel_name: Optional[str] = None
    author: Optional[str] = None
    author_id: Optional[int] = None
    attachment_names: list[str] = field(default_factory=list)
    scheduler_name: Optional[str] = None
    tick_type: str = "admin_message"  # admin_message | operational_check | deep_reflection
    harness: Optional[str] = None     # override harness for this event (None = use default)
    source_platform: str = "discord"
