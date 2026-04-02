import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, time, timedelta
from collections import Counter
import typing

# --- Pagination View ---
class StatsPaginator(discord.ui.View):
    def __init__(self, user_stats, channel_stats, total_messages, start_date, end_date):
        super().__init__(timeout=120)
        self.user_stats = user_stats
        self.channel_stats = channel_stats
        self.total_messages = total_messages
        self.start_date = start_date
        self.end_date = end_date
        self.current_page = 0
        self.per_page = 25
        self.max_pages = (len(user_stats) - 1) // self.per_page + 1

    def create_embed(self):
        embed = discord.Embed(
            title="📊 Extended Server Report",
            description=f"Period: `{self.start_date}` to `{self.end_date}`",
            color=discord.Color.blue()
        )
        
        # Summary & Channel Stats (Only on Page 1)
        if self.current_page == 0:
            embed.add_field(name="📈 Total Messages", value=f"**{self.total_messages}**", inline=False)
            
            top_channels = self.channel_stats.most_common(10)
            channel_list = "\n".join([f"**#{name}**: {count} msgs" for name, count in top_channels])
            embed.add_field(name="📂 Top Channels", value=channel_list or "No data", inline=False)
            embed.add_field(name="---", value="**User Leaderboard below:**", inline=False)

        # User Stats for current page
        start_idx = self.current_page * self.per_page
        end_idx = start_idx + self.per_page
        page_data = self.user_stats[start_idx:end_idx]
        
        user_list = "\n".join([f"{start_idx + i + 1}. **{name}**: {count} messages" for i, (name, count) in enumerate(page_data)])
        embed.add_field(name=f"👥 Users (Page {self.current_page + 1}/{self.max_pages})", value=user_list or "No more data", inline=False)
        
        embed.set_footer(text=f"Total Users: {len(self.user_stats)}")
        return embed

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.gray, disabled=True)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        await self.update_view(interaction)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.gray)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        await self.update_view(interaction)

    async def update_view(self, interaction: discord.Interaction):
        self.children[0].disabled = (self.current_page == 0)
        self.children[1].disabled = (self.current_page == self.max_pages - 1)
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

# --- Main Cog ---
class ServerStats(commands.GroupCog, name="stats"):
    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    @app_commands.command(name="generate", description="Generate server stats (today or custom range)")
    @app_commands.describe(
        today="If True, ignores start/end dates and shows stats for today only.",
        start_date="Format: YYYY-MM-DD",
        end_date="Format: YYYY-MM-DD",
        target_channel="Specific channel/thread to scan"
    )
    async def generate(
        self, 
        interaction: discord.Interaction, 
        today: bool = False,
        start_date: str = None, 
        end_date: str = None, 
        target_channel: typing.Union[discord.TextChannel, discord.VoiceChannel, discord.Thread, discord.ForumChannel] = None
    ):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Admin only.", ephemeral=True)

        # 1. Date Logic
        if today:
            now = datetime.now()
            start = datetime.combine(now.date(), time(0, 0, 0))
            end = datetime.combine(now.date(), time(23, 59, 59, 999999))
            # Set display strings for the embed
            start_date = start.strftime("%Y-%m-%d")
            end_date = end.strftime("%Y-%m-%d")
        else:
            if not start_date or not end_date:
                return await interaction.response.send_message("❌ Error: You must either set `today: True` or provide both `start_date` and `end_date`.", ephemeral=True)
            
            try:
                start = datetime.strptime(start_date, "%Y-%m-%d")
                end_base = datetime.strptime(end_date, "%Y-%m-%d")
                end = datetime.combine(end_base.date(), time(23, 59, 59, 999999))
            except ValueError:
                return await interaction.response.send_message("❌ Invalid date format. Use YYYY-MM-DD.", ephemeral=True)

        await interaction.response.defer()

        user_counts = Counter()
        channel_counts = Counter()
        total_messages = 0
        channels_to_scan = []

        # 2. Identify channels
        if target_channel:
            if isinstance(target_channel, discord.ForumChannel):
                channels_to_scan.extend(target_channel.threads)
                async for thread in target_channel.archived_threads(limit=None):
                    channels_to_scan.append(thread)
            else:
                channels_to_scan.append(target_channel)
        else:
            # Add basic text/voice channels and active threads
            channels_to_scan.extend(interaction.guild.text_channels)
            channels_to_scan.extend(interaction.guild.voice_channels)
            channels_to_scan.extend(interaction.guild.threads)
            
            # Add archived threads
            for channel in interaction.guild.channels:
                if isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
                    try:
                        async for thread in channel.archived_threads(limit=None):
                            channels_to_scan.append(thread)
                    except: continue

        # 3. Scanning
        for ch in channels_to_scan:
            if isinstance(ch, discord.ForumChannel): continue
            try:
                if hasattr(ch, 'history'):
                    async for message in ch.history(limit=None, after=start, before=end):
                        if not message.author.bot:
                            user_counts[message.author.display_name] += 1
                            # Attribute thread messages to parent channel
                            ch_parent = getattr(ch, 'parent', ch)
                            channel_counts[ch_parent.name] += 1
                            total_messages += 1
            except: continue

        if total_messages == 0:
            return await interaction.followup.send(f"No messages found for `{start_date}`.")

        # 4. Finalizing
        sorted_users = user_counts.most_common()
        view = StatsPaginator(sorted_users, channel_counts, total_messages, start_date, end_date)
        
        if view.max_pages <= 1:
            view.children[1].disabled = True
            
        await interaction.followup.send(embed=view.create_embed(), view=view)

async def setup(bot):
    await bot.add_cog(ServerStats(bot))