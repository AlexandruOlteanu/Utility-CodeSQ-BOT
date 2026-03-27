import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import io
from datetime import datetime, timedelta, timezone

# List of users who post the daily problems (excluded from streaks)
STAFF_USERS = ["781092774765396000"]

# --- Pagination & Sorting UI Class ---
class LeaderboardPagination(discord.ui.View):
    def __init__(self, filtered_data):
        super().__init__(timeout=180)
        self.filtered_data = filtered_data
        self.current_page = 1
        self.per_page = 20
        self.sort_key = "streak"  # Default sorting method
        self.sort_label = "Current Streak"
        self.sorted_users = []
        self.apply_sort()
        self.update_buttons()

    def apply_sort(self):
        """Sorts the data based on the selected criteria."""
        if self.sort_key == "streak":
            # Sort by current streak, then total solved
            self.sorted_users = sorted(
                self.filtered_data.items(),
                key=lambda x: (x[1].get('streak', 0), x[1].get('total_solved', 0)),
                reverse=True
            )
            self.sort_label = "Current Streak"
        elif self.sort_key == "highest_streak":
            # Sort by highest streak ever achieved
            self.sorted_users = sorted(
                self.filtered_data.items(),
                key=lambda x: (x[1].get('highest_streak', 0), x[1].get('streak', 0)),
                reverse=True
            )
            self.sort_label = "Best Streak"
        elif self.sort_key == "total_solved":
            # Sort by total problems solved (Total Days)
            self.sorted_users = sorted(
                self.filtered_data.items(),
                key=lambda x: (x[1].get('total_solved', 0), x[1].get('streak', 0)),
                reverse=True
            )
            self.sort_label = "Total Days"

        self.total_pages = max(1, (len(self.sorted_users) + self.per_page - 1) // self.per_page)

    def update_buttons(self):
        """Enables or disables navigation buttons."""
        self.prev_button.disabled = self.current_page == 1
        self.next_button.disabled = self.current_page == self.total_pages

    def generate_embed(self):
        """Generates the leaderboard embed for the current page."""
        embed = discord.Embed(
            title="🏆 Problems of the Day - Leaderboard", 
            color=0xFFD700
        )
        
        start_idx = (self.current_page - 1) * self.per_page
        end_idx = start_idx + self.per_page
        page_users = self.sorted_users[start_idx:end_idx]
        
        lb_description = f"Sorting by: **{self.sort_label}**\n\n"
        for i, (uid, data) in enumerate(page_users, start=start_idx + 1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, "🔹")
            lb_description += (
                f"{medal} **#{i}** - <@{uid}>\n"
                f"└ 🔥 Current: `{data['streak']}` | ⭐ Best: `{data.get('highest_streak', 0)}` | 📈 Total: `{data.get('total_solved', 0)}` d\n\n"
            )

        if not page_users:
            lb_description += "No users found on this page."
            
        embed.description = lb_description
        embed.set_footer(text=f"Page {self.current_page} of {self.total_pages} | Utility Codesquare")
        return embed

    @discord.ui.select(
        placeholder="Choose sorting criteria...",
        options=[
            discord.SelectOption(label="Current Streak", value="streak", emoji="🔥", description="Sort by active daily streak"),
            discord.SelectOption(label="Best Streak", value="highest_streak", emoji="⭐", description="Sort by all-time highest streak"),
            discord.SelectOption(label="Total Days", value="total_solved", emoji="📈", description="Sort by total days completed")
        ]
    )
    async def sort_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        """Handles the selection of a new sorting method."""
        self.sort_key = select.values[0]
        self.current_page = 1  # Reset to page 1 on resort
        self.apply_sort()
        self.update_buttons()
        await interaction.response.edit_message(embed=self.generate_embed(), view=self)

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
        """Saves current state to the JSON file."""
        with open(self.data_file, 'w') as f:
            json.dump(self.streak_data, f, indent=4)

    @app_commands.command(name="process-problems-odd-streak", description="Processes today's streaks and applies a 24h grace period.")
    @app_commands.describe(target_date="The processing date (YYYY-MM-DD)")
    @app_commands.checks.has_permissions(administrator=True)
    async def process_problems_odd_streak(self, interaction: discord.Interaction, target_date: str):
        await interaction.response.defer(ephemeral=True)
        
        try:
            current_dt = datetime.strptime(target_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            previous_dt = current_dt - timedelta(days=1)
            
            start_scan = datetime.combine(previous_dt.date(), datetime.min.time(), tzinfo=timezone.utc)
            end_scan = datetime.combine(current_dt.date(), datetime.max.time(), tzinfo=timezone.utc)
            
            target_date_str = str(current_dt.date())
            day_before_grace = (previous_dt - timedelta(days=1)).date()
        except ValueError:
            await interaction.followup.send("❌ Invalid format. Use YYYY-MM-DD (e.g., 2026-03-22).")
            return

        active_users_in_scan = set()
        new_points = 0

        async for msg in interaction.channel.history(after=start_scan, before=end_scan, oldest_first=True):
            u_id = str(msg.author.id)
            if u_id in STAFF_USERS:
                continue

            content = msg.content.lower()
            if "https://codeforces" in content and "submission" in content:
                if u_id in active_users_in_scan:
                    continue
                
                if u_id not in self.streak_data:
                    self.streak_data[u_id] = {"streak": 0, "highest_streak": 0, "total_solved": 0, "last_date": None}

                user = self.streak_data[u_id]
                last_str = user.get("last_date")
                
                if last_str == target_date_str:
                    active_users_in_scan.add(u_id)
                    continue

                last_solve_date = datetime.strptime(last_str, "%Y-%m-%d").date() if last_str else None

                if last_solve_date and last_solve_date >= day_before_grace:
                    user["streak"] += 1
                else:
                    user["streak"] = 1

                user["total_solved"] = user.get("total_solved", 0) + 1
                if user["streak"] > user.get("highest_streak", 0):
                    user["highest_streak"] = user["streak"]

                user["last_date"] = target_date_str
                active_users_in_scan.add(u_id)
                new_points += 1
                
                try:
                    await msg.add_reaction("🔥")
                except:
                    pass

        reset_count = 0
        for u_id, data in self.streak_data.items():
            if u_id in STAFF_USERS:
                continue
            
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

    @app_commands.command(name="leaderboard-problems-of-the-day", description="View rankings with selectable sorting.")
    async def leaderboard_problems_of_the_day(self, interaction: discord.Interaction):
        if not self.streak_data:
            await interaction.response.send_message("The leaderboard is currently empty. 🚀")
            return

        filtered_data = {uid: data for uid, data in self.streak_data.items() if uid not in STAFF_USERS}
        
        if not filtered_data:
            await interaction.response.send_message("No valid users found. 🚀")
            return

        view = LeaderboardPagination(filtered_data)
        embed = view.generate_embed()
        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(ProblemsOfTheDayStreak(bot))