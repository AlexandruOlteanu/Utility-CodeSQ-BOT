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
    @app_commands.command(name="process-problems-odd-streak", description="Process today and yesterday's grace period. Resets inactive users to 0.")
    @app_commands.describe(target_date="The main processing date (YYYY-MM-DD)")
    @app_commands.checks.has_permissions(administrator=True)
    async def process_problems_odd_streak(self, interaction: discord.Interaction, target_date: str):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Reference date
            current_dt = datetime.strptime(target_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            # Grace period date (yesterday)
            previous_dt = current_dt - timedelta(days=1)
            
            # Scan interval: Start of yesterday 00:00 -> End of today 23:59 (UTC)
            start_scan = datetime.combine(previous_dt.date(), datetime.min.time(), tzinfo=timezone.utc)
            end_scan = datetime.combine(current_dt.date(), datetime.max.time(), tzinfo=timezone.utc)
            
            target_date_str = str(current_dt.date())
            day_before_grace = (previous_dt - timedelta(days=1)).date()
        except ValueError:
            await interaction.followup.send("❌ Invalid format. Please use YYYY-MM-DD (e.g., 2026-03-22).")
            return

        active_users_in_scan = set()
        new_points = 0

        # 1. SCAN MESSAGES (48h Window)
        async for msg in interaction.channel.history(after=start_scan, before=end_scan, oldest_first=True):
            u_id = str(msg.author.id)
            if u_id in STAFF_USERS:
                continue

            content = msg.content.lower()
            if "https://codeforces" in content and "submission" in content:
                # If already processed this user in this scan, skip
                if u_id in active_users_in_scan:
                    continue
                
                if u_id not in self.streak_data:
                    self.streak_data[u_id] = {"streak": 0, "highest_streak": 0, "total_solved": 0, "last_date": None}

                user = self.streak_data[u_id]
                last_str = user.get("last_date")
                
                # If they already have a record for this exact target date from a previous run, skip
                if last_str == target_date_str:
                    active_users_in_scan.add(u_id)
                    continue

                last_solve_date = datetime.strptime(last_str, "%Y-%m-%d").date() if last_str else None

                # STREAK LOGIC:
                # Since yesterday is grace, we increment if last solve was day before yesterday or yesterday
                if last_solve_date and last_solve_date >= day_before_grace:
                    user["streak"] += 1
                else:
                    user["streak"] = 1

                user["total_solved"] = user.get("total_solved", 0) + 1
                if user["streak"] > user.get("highest_streak", 0):
                    user["highest_streak"] = user["streak"]

                # We "move" their solve date to the target_date
                user["last_date"] = target_date_str
                active_users_in_scan.add(u_id)
                new_points += 1
                
                try:
                    await msg.add_reaction("🔥")
                except:
                    pass

        # 2. RESET LOGIC (Zero out users who missed the 48h window)
        reset_count = 0
        for u_id, data in self.streak_data.items():
            if u_id in STAFF_USERS:
                continue
            
            # If the user was NOT active in the window we just scanned
            if u_id not in active_users_in_scan:
                if data.get("streak", 0) > 0:
                    data["streak"] = 0
                    reset_count += 1

        self.save_data()
        await interaction.followup.send(
            f"✅ **Processing complete for `{target_date_str}`**\n"
            f"└ 🔸 Active users (including grace): `{len(active_users_in_scan)}` (`{new_points}` newly updated)\n"
            f"└ 💀 Inactive users reset to 0: `{reset_count}`"
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