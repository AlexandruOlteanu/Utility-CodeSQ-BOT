# 🛠️ Technical Administration Manual - Utility CodeSQ

This document contains all necessary procedures for managing the bot on Arch Linux, including service control, environment management, and troubleshooting.

---

## 🚀 1. Service Management (systemd)

The bot runs as a background service named `codesquare-bot`. This ensures automatic restart in case of crashes or system reboots.

| Action      | Command                                 | Description                                        |
| :---------- | :-------------------------------------- | :------------------------------------------------- |
| **Restart** | `sudo systemctl restart codesquare-bot` | Use after modifying `.py` or `.env` files.         |
| **Status**  | `sudo systemctl status codesquare-bot`  | Check if the bot is running or if errors occurred. |
| **Stop**    | `sudo systemctl stop codesquare-bot`    | Completely stops the bot.                          |
| **Start**   | `sudo systemctl start codesquare-bot`   | Starts the bot if it was manually stopped.         |
| **Enable**  | `sudo systemctl enable codesquare-bot`  | Enables auto-start at system boot.                 |

---

## 📜 2. Monitoring and Logs (Debugging)

To monitor the bot in real time (processed messages, Python errors, login status), use `journalctl`:

### **Live Log Stream**

```bash
sudo journalctl -u codesquare-bot -f
```

### **Last 50 Lines (No Scroll)**

```bash
sudo journalctl -u codesquare-bot -n 50 --no-pager
```

---

## 📦 3. Virtual Environment Management (venv)

All dependencies (e.g., `discord.py`, `python-dotenv`) must be installed inside the virtual environment to avoid conflicts with the Arch system.

### **Activate the Environment**

Before running any `pip` command:

```bash
cd /home/alexandruinv/Alex/CodeSquare/UtilityBot/
source venv/bin/activate
```

### **Install Dependencies**

If you add new modules or encounter `ModuleNotFoundError`:

```bash
# Install from requirements file
pip install -r requirements.txt

# Manually install critical modules
pip install discord.py python-dotenv
```
