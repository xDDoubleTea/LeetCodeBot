import os

from dotenv import load_dotenv

load_dotenv()


def get_required_secret(key: str) -> str:
    value = os.getenv(key)
    if value is None:
        raise OSError(f"Required secret '{key}' is not set in environment variables.")
    return value


def secret_flag(key: str, default: bool = False) -> bool:
    """
    Read an on/off setting as a bool.

    Environment variables are always strings, and a bare string is the wrong type
    here twice over: "False" is truthy, and create_async_engine(echo=...) rejects
    anything that is not a bool or one of its own keywords.
    """
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


bot_token = get_required_secret("BOT_TOKEN")
DATABASE_URL = get_required_secret("DATABASE_URL")
debug = secret_flag("DEBUG", False)
