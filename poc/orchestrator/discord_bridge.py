import asyncio

from pathlib import Path

import discord

from .models import AgentEvent
from .phone_book import PhoneBook


class DiscordBridge(discord.Client):
    def __init__(self, config: dict, event_queue: asyncio.Queue, vault_dir: Path):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.dm_messages = True
        intents.members = True  # Needed to iterate guild members
        super().__init__(intents=intents)
        self.config = config
        self.event_queue = event_queue
        self.vault_dir = vault_dir
        self.phone_book = PhoneBook(vault_dir)
        self._reply_channels: dict[str, int] = {}  # correlation: channel_id
        self._last_channel_id: int | None = None

    async def on_ready(self):
        print(f"[discord] Logged in as {self.user}")
        # Update from guilds
        for guild in self.guilds:
            self.phone_book.update_from_guild(guild)
        # Update from all users the bot can see (captures DM-only contacts if cached)
        for user in self.users:
            self.phone_book.update_from_dm(user)
        self.phone_book.render()

    async def on_message(self, message: discord.Message):
        if message.author == self.user:
            return

        # Update phone book from message authors to capture DM contacts not in any guild
        if self.phone_book.update_from_dm(message.author):
            self.phone_book.render()

        if not self._should_process(message):
            return

        # Store reply channel for routing responses back
        # Use a simple last-channel-wins approach for now
        self._last_channel_id = message.channel.id

        event = AgentEvent(
            event_type="discord_message",
            prompt=message.content,
            channel_id=message.channel.id,
            channel_name=str(message.channel),
            author=str(message.author),
            author_id=message.author.id,
            attachment_names=[a.filename for a in message.attachments],
            tick_type="admin_message",
            source_platform="discord",
        )
        await self.event_queue.put(event)

    def _should_process(self, message: discord.Message) -> bool:
        """Filter messages based on config allowed_sources."""
        allowed = self.config.get("allowed_sources", {})

        # Allow DMs
        if isinstance(message.channel, discord.DMChannel):
            dm_config = allowed.get("dms", {})
            if not dm_config.get("enabled", True):
                return False
            allowed_users = dm_config.get("user_ids", [])
            if allowed_users and message.author.id not in allowed_users:
                return False
            return True

        # Allow group DMs
        if isinstance(message.channel, discord.GroupChannel):
            return allowed.get("group_dms", {}).get("enabled", False)

        # Allow specific server channels
        if hasattr(message.channel, "guild"):
            server_channels = allowed.get("server_channels", [])
            if message.channel.id not in server_channels:
                return False
            mention_only = allowed.get("mention_only", True)
            if mention_only and self.user not in message.mentions:
                return False
            return True

        return False

    async def send_to_discord(self, channel_id: int, text: str):
        """Send a message to a Discord channel, chunking if needed."""
        channel = self.get_channel(channel_id)
        if channel is None:
            channel = await self.fetch_channel(channel_id)

        # Discord 2000 char limit — chunk if needed
        chunks = _chunk_message(text, 1900)
        for chunk in chunks:
            await channel.send(chunk)


def _chunk_message(text: str, max_len: int = 1900) -> list[str]:
    """Split message into chunks respecting Discord's character limit."""
    if len(text) <= max_len:
        return [text]
    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks
