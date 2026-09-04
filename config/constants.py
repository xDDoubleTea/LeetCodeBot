import datetime

import discord

COMMAND_PREFIX = ">"
LEETCODE_VERIFY_TOKEN_PREFIX = "leetcodebot-verify"

tz = datetime.timezone(datetime.timedelta(hours=8))
LEETCODE_API_REFRESH_TIME = datetime.time(hour=8, minute=5, tzinfo=tz)
# Replace with your guild ID.
MY_GUILD = discord.Object(1039906085626196079)

# For embed description
PREVIEW_LEN = 4000

# /migrate: one forum scan per guild per five minutes. archived_threads(limit=None)
# walks every archived post in the channel, so the cost grows with the forum rather
# than being fixed, and the result barely changes between two runs a minute apart.
MIGRATE_SCAN_RATE = 1
MIGRATE_SCAN_PER = 300.0

# /problem, /daily and /random: three thread creations per member per guild per
# thirty seconds. Each one can create a forum thread and its starter message, so
# repeated calls spend against Discord's channel-creation limits, and a member who
# keeps invoking a command that fails the same way every time posts the reply into
# the channel each attempt.
THREAD_COMMAND_RATE = 3
THREAD_COMMAND_PER = 30.0

# Should be applied to commands that calls LeetCode API
USER_INFO_COMMAND_RATE = 3
USER_INFO_COMMAND_PER = 60.0

# Replace with your Discord user ID.
# This is used for development only, the actual features should not depend on this!
DEV_ID = 398444155132575756


THEME_COLOR = discord.Color.green()

LOG_DIR = "logs"
BOT_LOG_FILE_NAME = "bot.log"
SQLALCHEMY_LOG_FILE_NAME = "sqlalchemy.log"

BOT_NAME = "LeetCodeBot"

VERSION = "0.6.7"
DEFAULT_FOOTER = f"LeetCodeBot version:{VERSION}"
