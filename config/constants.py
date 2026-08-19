import discord
import datetime

command_prefix = ">"

tz = datetime.timezone(datetime.timedelta(hours=8))
LEETCODE_API_REFRESH_TIME = datetime.time(hour=8, minute=5, tzinfo=tz)
MY_GUILD = discord.Object(1039906085626196079)  # Replace with your guild ID
PREVIEW_LEN = 4000

DEV_ID = 398444155132575756  # Replace with your Discord user ID
THEME_COLOR = discord.Color.green()

bot_name = "LeetCodeBot"

version = "0.6.7"
default_footer = f"LeetCodeBot version:{version}"
