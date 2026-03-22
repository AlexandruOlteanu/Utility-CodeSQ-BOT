import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import io
from datetime import datetime, timedelta, timezone

# List of users who post the daily problems (excluded from streaks)
STAFF_USERS = ["781092774765396000"]

# --- NEW: Pagination UI Class ---
class LeaderboardPagination(discord.ui.View):
    def __init__(self, sorted_users):
        super().__init__(timeout=180) # The buttons will stop working after 3 minutes to save memory
        self.sorted_users = sorted_users
        self.current_page = 1
        self.per_page = 20
        self.total_pages = max(1, (len(self.sorted_users) + self.per_page - 1) // self.per_page)
        
        self.update_buttons()

    def update_buttons(self):
        """Enables or disables buttons depending on the current page."""
        self.prev_button.disabled = self.current_page == 1
        self.next_button.disabled = self.current_page == self.total_pages

    def generate_embed(self):
        """Generates the embed for the current page."""
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

    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.primary, custom_id="prev")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.generate_embed(), view=self)

    @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.primary, custom_id="next")
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
        """Safely loads the JSON database, handling empty or corrupted files."""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, io.UnsupportedOperation):
                return {}
        return {}

    def save_data(self):
        """Saves current state to problemsOfTheDayStreak.json."""
        with open(self.data_file, 'w') as f:
            json.dump(self.streak_data, f, indent=4)

    # --- COMMAND: /process-problems-odd-streak ---
    @app_commands.command(name="process-problems-odd-streak", description="Scan all messages for CF submissions on a specific UTC date.")
    @app_commands.describe(target_date="The date to process (YYYY-MM-DD)")
    @app_commands.checks.has_permissions(administrator=True)
    async def process_problems_odd_streak(self, interaction: discord.Interaction, target_date: str):
        await interaction.response.defer(ephemeral=True)
        
        try:
            target_dt = datetime.strptime(target_date, "%Y-%m-%d")
            credit_date = target_dt.date()
            yesterday = credit_date - timedelta(days=1)

            start_of_day = datetime.combine(credit_date, datetime.min.time(), tzinfo=timezone.utc)
            end_of_day = start_of_day + timedelta(days=1)
        except ValueError:
            await interaction.followup.send("❌ Invalid format. Please use YYYY-MM-DD (e.g., 2026-03-22).")
            return

        users_processed_this_scan = set()
        new_points = 0

        async for msg in interaction.channel.history(after=start_of_day, before=end_of_day, oldest_first=True):
            u_id = str(msg.author.id)
            
            if u_id in STAFF_USERS:
                continue

            content = msg.content.lower()
            if "https://codeforces" in content and "submission" in content:
                if u_id in users_processed_this_scan:
                    continue
                
                if u_id not in self.streak_data:
                    self.streak_data[u_id] = {"streak": 0, "highest_streak": 0, "total_solved": 0, "last_date": None}

                user = self.streak_data[u_id]
                last_str = user.get("last_date")
                last_date = datetime.strptime(last_str, "%Y-%m-%d").date() if last_str else None

                if last_date == credit_date:
                    users_processed_this_scan.add(u_id)
                    continue

                user["total_solved"] = user.get("total_solved", 0) + 1
                user["streak"] = user["streak"] + 1 if last_date == yesterday else 1

                if user["streak"] > user.get("highest_streak", 0):
                    user["highest_streak"] = user["streak"]

                user["last_date"] = str(credit_date)
                users_processed_this_scan.add(u_id)
                new_points += 1
                
                try:
                    await msg.add_reaction("🔥")
                except:
                    pass

        self.save_data()
        await interaction.followup.send(f"✅ Date `{target_date}` processed. `{new_points}` solvers credited for this UTC day.")

    # --- COMMAND: /leaderboard-problems-of-the-day ---
    @app_commands.command(name="leaderboard-problems-of-the-day", description="Rank users by current streak and total solved.")
    async def leaderboard_problems_of_the_day(self, interaction: discord.Interaction):
        if not self.streak_data:
            await interaction.response.send_message("The leaderboard is empty. 🚀")
            return

        # Exclude STAFF_USERS
        filtered_data = {uid: data for uid, data in self.streak_data.items() if uid not in STAFF_USERS}
        
        # We removed the [:10] limit so ALL users are loaded into the list
        sorted_users = sorted(
            filtered_data.items(), 
            key=lambda x: (x[1].get('streak', 0), x[1].get('total_solved', 0)), 
            reverse=True
        )

        if not sorted_users:
            await interaction.response.send_message("The leaderboard is empty (no valid users found). 🚀")
            return

        # Create the paginated view and generate the first page
        view = LeaderboardPagination(sorted_users)
        embed = view.generate_embed()
        
        # Send the message with the embed AND the interactive buttons attached
        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(ProblemsOfTheDayStreak(bot))