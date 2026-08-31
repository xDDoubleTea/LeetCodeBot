# Loaded before any test module is imported, which is the point: five cogs import
# main at module scope, and main imports config.secrets, which raises when
# BOT_TOKEN is unset. CI has no .env, so collecting such a test used to bring the
# whole suite down at collection time rather than failing one test.
#
# setdefault, not assignment: anything already exported into the environment wins,
# so this cannot quietly override a developer's own values.
import os

os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
