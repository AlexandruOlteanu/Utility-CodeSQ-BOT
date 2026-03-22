import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import io
from datetime import datetime, timedelta, timezone

# List of users who post the daily problems (excluded from streaks)
STAFF_USERS = ["781092774765396000"]

# --- Pagination UI Class ---
class LeaderboardPagination(discord.ui.View):
    def __init__(self, sorted_users):
        super().__init__(timeout=180)
        self.sorted_users = sorted_users
        self.current_page = 1
        self.per_page = 20
        self.total_pages = max(1, (len(self.sorted_users) + self.per_page - 1) // self.per_page)
        self.update_buttons()

    def update_buttons(self):
        """Enables or disables buttons based on the current page."""
        self.prev_button.disabled = self.current_page == 1
        self.next_button.disabled = self.current_page == self.total_pages

    def generate_embed(self):
        """Generates the leaderboard embed for the current page."""
        embed = discord.Embed(title="🏆 Problems of the Day - Leaderboard", color=0xFFD700)
        
        start_idx = (self.current_page - 1) * self.per_page
        end_idx = start_idx + self.per_page
        page_users = self.sorted_users[start_idx:end_idx]
        
        lb_description = ""
        for i, (uid, data) in enumerate(page_users, start=start_idx + 1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, "🔹")
            lb_description += (
                f"{medal} **#{i}** - <@{uid}>\n"
                f"└ 🔥 Streak: `{data['streak']}` | ⭐ Best: `{data.get('highest_streak', 0)}` | 📈 Total: `{data.get('total_solved', 0)}`\n\n"
            )

        if not lb_description:
            lb_description = "No users found on this page."
            
        embed.description = lb_description
        embed.set_footer(text=f"Page {self.current_page} of {self.total_pages} | Utility Codesquare - BOT")
        return embed

    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.primary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.generate_embed(), view=self)

    @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.generate_embed(), view=self)


class ProblemsOfTheDayStreak(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_file = 'problemsOfTheDayStreak.json'
        self.streak_data = self.load_data()

    def load_data(self):
        """Loads the JSON database, handling missing or corrupted files."""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, io.UnsupportedOperation):
                return {}
        return {}

    def save_data(self):
        """Saves the current state to the JSON file."""
        with open(self.data_file, 'w') as f:
            json.dump(self.streak_data, f, indent=4)

    # --- COMMAND: /process-problems-odd-streak ---
    @app_commands.command(name="process-problems-odd-streak", description="Scan messages from the target and previous day to validate streaks.")
    @app_commands.describe(target_date="The main date in YYYY-MM-DD format")
    @app_commands.checks.has_permissions(administrator=True)
    async def process_problems_odd_streak(self, interaction: discord.Interaction, target_date: str):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Reference date ("Today")
            current_dt = datetime.strptime(target_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            # Reference date ("Yesterday")
            previous_dt = current_dt - timedelta(days=1)
            
            # Scanning interval: Start of yesterday 00:00 -> End of today 23:59 (UTC)
            start_scan = datetime.combine(previous_dt.date(), datetime.min.time(), tzinfo=timezone.utc)
            end_scan = datetime.combine(current_dt.date(), datetime.max.time(), tzinfo=timezone.utc)
        except ValueError:
            await interaction.followup.send("❌ Invalid format. Please use YYYY-MM-DD (e.g., 2026-03-22).")
            return

        new_points = 0
        # Prevents double counting the same user for the same calendar day
        processed_entries = set()

        # oldest_first=True is CRITICAL to process "yesterday" before "today"
        async for msg in interaction.channel.history(after=start_scan, before=end_scan, oldest_first=True):
            u_id = str(msg.author.id)
            
            if u_id in STAFF_USERS:
                continue

            content = msg.content.lower()
            if "https://codeforces" in content and "submission" in content:
                msg_date = msg.created_at.date()
                entry_key = f"{u_id}:{msg_date}"

                # If the user posted multiple links on the same day, only count once
                if entry_key in processed_entries:
                    continue
                
                if u_id not in self.streak_data:
                    self.streak_data[u_id] = {"streak": 0, "highest_streak": 0, "total_solved": 0, "last_date": None}

                user = self.streak_data[u_id]
                last_str = user.get("last_date")
                last_date = datetime.strptime(last_str, "%Y-%m-%d").date() if last_str else None

                # Only process if this message is newer than the last recorded date in DB
                if last_date is None or msg_date > last_date:
                    # If it's exactly the day after the last recorded solve, increment streak
                    if last_date and msg_date == last_date + timedelta(days=1):
                        user["streak"] += 1
                    else:
                        # If a day was skipped or it's their first time, reset streak to 1
                        user["streak"] = 1

                    user["total_solved"] = user.get("total_solved", 0) + 1
                    
                    if user["streak"] > user.get("highest_streak", 0):
                        user["highest_streak"] = user["streak"]

                    user["last_date"] = str(msg_date)
                    processed_entries.add(entry_key)
                    new_points += 1
                    
                    try:
                        await msg.add_reaction("🔥")
                    except:
                        pass

        self.save_data()
        await interaction.followup.send(
            f"✅ Scan complete for interval `{previous_dt.date()}` -> `{current_dt.date()}`.\n"
            f"📈 `{new_points}` new streak points were processed chronologically."
        )

    # --- COMMAND: /leaderboard-problems-of-the-day ---
    @app_commands.command(name="leaderboard-problems-of-the-day", description="View user rankings based on streaks and total solved.")
    async def leaderboard_problems_of_the_day(self, interaction: discord.Interaction):
        if not self.streak_data:
            await interaction.response.send_message("The leaderboard is currently empty. 🚀")
            return

        filtered_data = {uid: data for uid, data in self.streak_data.items() if uid not in STAFF_USERS}
        
        sorted_users = sorted(
            filtered_data.items(), 
            key=lambda x: (x[1].get('streak', 0), x[1].get('total_solved', 0)), 
            reverse=True
        )

        if not sorted_users:
            await interaction.response.send_message("No valid users found for the leaderboard. 🚀")
            return

        view = LeaderboardPagination(sorted_users)
        embed = view.generate_embed()
        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(ProblemsOfTheDayStreak(bot))