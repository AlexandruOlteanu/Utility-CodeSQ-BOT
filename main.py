import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv

# Load the variables from the .env file
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

class UtilityBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        super().__init__(
            command_prefix="!", 
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):
        print("--- Loading Modules ---")
        if not os.path.exists('./cogs'):
            os.makedirs('./cogs')

        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    print(f'✅ Loaded Cog: {filename}')
                except Exception as e:
                    print(f'❌ Failed to load {filename}: {e}')
        
        print("--- Syncing Slash Commands ---")
        await self.tree.sync()
        print("✨ System Ready.")


async def run_bot():
    bot = UtilityBot()
    async with bot:
        if not TOKEN:
            print("❌ ERROR: DISCORD_TOKEN not found in .env file.")
            return
        await bot.start(TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        print("Bot is shutting down...")