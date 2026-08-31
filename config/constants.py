import datetime

import discord

command_prefix = ">"

tz = datetime.timezone(datetime.timedelta(hours=8))
LEETCODE_API_REFRESH_TIME = datetime.time(hour=8, minute=5, tzinfo=tz)
MY_GUILD = discord.Object(1039906085626196079)  # Replace with your guild ID

# For embed description
PREVIEW_LEN = 4000

# /migrate: one forum scan per guild per five minutes. archived_threads(limit=None)
# walks every archived post in the channel, so the cost grows with the forum rather
# than being fixed, and the result barely changes between two runs a minute apart.
MIGRATE_SCAN_RATE = 1
MIGRATE_SCAN_PER = 300.0

DEV_ID = 398444155132575756  # Replace with your Discord user ID

THEME_COLOR = discord.Color.green()

LOG_DIR = "logs"
BOT_LOG_FILE_NAME = "bot.log"
SQLALCHEMY_LOG_FILE_NAME = "sqlalchemy.log"

bot_name = "LeetCodeBot"

version = "0.6.7"
default_footer = f"LeetCodeBot version:{version}"
