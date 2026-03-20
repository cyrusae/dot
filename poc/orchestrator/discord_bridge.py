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
        self._channel_members: dict[int, list[str]] = {}  # channel_id: [participant_ids]

    async def on_ready(self):
        print(f"[discord] Logged in as {self.user}")
        # Update from guilds
        for guild in self.guilds:
            self.phone_book.update_from_guild(guild)
            # Update member cache for all text channels in this guild
            for channel in guild.text_channels:
                self._update_member_cache(channel)

        # Update from all users the bot can see (captures DM-only contacts if cached)
        for user in self.users:
            self.phone_book.update_from_dm(user)
        self.phone_book.render()

    def _update_member_cache(self, channel):
        """Update the list of participant IDs for a channel, excluding the bot."""
        if hasattr(channel, "members"):
            self._channel_members[channel.id] = [
                f"discord:{member.id}"
                for member in channel.members
                if member.id != self.user.id
            ]

    async def on_member_join(self, member):
        """Update cache when someone joins a guild."""
        for channel in member.guild.text_channels:
            self._update_member_cache(channel)

    async def on_message(self, message: discord.Message):
        if message.author == self.user:
            return

        # Update phone book from message authors to capture DM contacts not in any guild
        if self.phone_book.update_from_dm(message.author):
            self.phone_book.render()

        print(f"[discord] on_message: channel={message.channel} ({type(message.channel).__name__}) "
              f"author={message.author} mentions={[u.id for u in message.mentions]} "
              f"bot_id={self.user.id if self.user else None} "
              f"content_preview={message.content[:50]!r}", flush=True)

        if not self._should_process(message):
            print(f"[discord] _should_process returned False, skipping", flush=True)
            return

        # Store reply channel for routing responses back
        # Use a simple last-channel-wins approach for now
        self._last_channel_id = message.channel.id

        # Compute conversation_id and participant_ids
        conversation_id = None
        participant_ids = []
        if isinstance(message.channel, discord.DMChannel):
            conversation_id = f"discord:dm:{message.author.id}"
            participant_ids = [f"discord:{message.author.id}"]
        elif hasattr(message.channel, "guild"):
            conversation_id = f"discord:ch:{message.channel.id}"
            # Refresh cache if not present
            if message.channel.id not in self._channel_members:
                self._update_member_cache(message.channel)
            participant_ids = self._channel_members.get(message.channel.id, [])

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
            conversation_id=conversation_id,
            participant_ids=participant_ids,
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
            if mention_only:
                bot_id = self.user.id
                user_mentioned = any(u.id == bot_id for u in message.mentions)
                mention_role_ids = set(allowed.get("mention_role_ids", []))
                role_mentioned = any(r.id in mention_role_ids for r in message.role_mentions)
                if not user_mentioned and not role_mentioned:
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
