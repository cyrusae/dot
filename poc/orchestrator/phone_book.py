from __future__ import annotations

import discord
from pathlib import Path


class PhoneBook:
    def __init__(self, vault_dir: Path):
        self.vault_dir = vault_dir
        self.people: dict[int, dict[str, str]] = {}
        self.channels: dict[int, dict[str, str]] = {}

    def update_from_guild(self, guild: discord.Guild) -> bool:
        """Update people and channels from a guild. Returns True if changed."""
        changed = False
        # Update members
        for member in guild.members:
            person = {
                "name": member.name,
                "display_name": member.display_name,
                "id": str(member.id),
            }
            if self.people.get(member.id) != person:
                self.people[member.id] = person
                changed = True
        
        # Update channels
        for channel in guild.channels:
            if isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.StageChannel, discord.Thread)):
                ch = {
                    "name": channel.name,
                    "type": str(channel.type),
                    "id": str(channel.id),
                }
                if self.channels.get(channel.id) != ch:
                    self.channels[channel.id] = ch
                    changed = True
        return changed

    def update_from_dm(self, user: discord.User | discord.Member) -> bool:
        """Update a person from a DM contact. Returns True if changed."""
        person = {
            "name": user.name,
            "display_name": getattr(user, "display_name", user.name),
            "id": str(user.id),
        }
        if self.people.get(user.id) != person:
            self.people[user.id] = person
            return True
        return False

    def render(self):
        """Render the phone book to a markdown file."""
        output_dir = self.vault_dir / "people"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "phone-book.md"

        lines = [
            "# Phone Book",
            "",
            "Auto-generated on startup. Use Discord IDs to look up people/ vault notes.",
            "",
            "## People",
            "| Name | Display Name | Discord ID |",
            "|---|---|---|",
        ]

        # Sort people by display name
        sorted_people = sorted(self.people.values(), key=lambda p: p["display_name"].lower())
        for person in sorted_people:
            lines.append(f"| {person['name']} | {person['display_name']} | {person['id']} |")

        lines.append("")
        lines.append("## Channels")
        lines.append("| Name | Type | Channel ID |")
        lines.append("|---|---|---|")

        # Sort channels by name
        sorted_channels = sorted(self.channels.values(), key=lambda c: c["name"].lower())
        for channel in sorted_channels:
            lines.append(f"| {channel['name']} | {channel['type']} | {channel['id']} |")

        output_file.write_text("\n".join(lines), encoding="utf-8")
