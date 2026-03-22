# 🤖 Utility CodeSQ - BOT

A specialized Discord bot built with `discord.py` to track competitive programming consistency, manage Codeforces (CF) submission streaks, and handle administrative message exports.

---

## 📂 Project Structure

The bot uses a **Cogs** architecture to keep logic separated and organized.

* **`main.py`**: The central hub. It initializes the bot, sets intents, loads all modules from the `/cogs` folder, and syncs Slash Commands with Discord.
* **`cogs/problemsOfTheDayStreak.py`**: The engine. Contains logic for history scanning, streak math, and the leaderboard.
* **`streaks.json`**: The database. A local JSON file storing User IDs, solve counts, and streak data.

---

## 🚀 Local Deployment (Arch Linux)

The bot is configured to run as a **systemd service**, ensuring it stays online 24/7 and restarts automatically if the system reboots.

### 1. Service File Location
The service configuration is located at:
`/etc/systemd/system/codesquare-bot.service`

### 2. Service Template
```ini
[Unit]
Description=Utility CodeSQ Discord Bot
After=network.target

[Service]
User=alexandruinv
WorkingDirectory=/home/alexandruinv/Alex/CodeSquare/UtilityBot
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target