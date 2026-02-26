# Discord server leave GUI

**Leave Discord servers in bulk.** Desktop app that lists your servers and lets you select which to leave, with a configurable delay between each so you don’t hit rate limits. For cleaning up a long server list, automating leaves, or leaving many servers without clicking one-by-one.

## TL;DR

```bash
git clone https://github.com/jacobdcook/discord-guild-leave-gui.git
cd discord-guild-leave-gui
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# Put your Discord user token in token.txt (one line), then:
.venv/bin/python guild_leave_gui.py
```

## Getting your token

**User token** (your account — not a bot token):

1. Open Discord in your **browser** (not the desktop app): https://discord.com/app
2. Log in, then press **F12** (DevTools) → **Application** tab (or Storage)
3. **Local Storage** → select `https://discord.com`
4. Find the key that looks like a long token (often named `token` or similar) and copy its value.

Alternatively search for “how to get Discord user token” — same idea (localStorage / client).

**Important:** Using a user token for automation is against Discord’s ToS; use at your own risk. Never share your token or commit `token.txt` (it’s in `.gitignore`).

## Usage

1. Paste your token in the field (or in `token.txt` — first non-comment line). Use **Save token to file** to persist it.
2. Click **Load my servers**. Your servers appear with icons.
3. Check the ones you want to leave. Use **Select all** / **Deselect all** if needed.
4. Set **Delay between each leave** (seconds). Default 3.
5. Click **Leave selected** and confirm.

## Requirements

- Python 3.10+
- aiohttp, Pillow (see `requirements.txt`)
