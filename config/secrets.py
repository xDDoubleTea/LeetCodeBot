from dotenv import load_dotenv
import os

load_dotenv()


def get_required_secret(key: str) -> str:
    value = os.getenv(key)
    if value is None:
        raise EnvironmentError(
            f"Required secret '{key}' is not set in environment variables."
        )
    return value


bot_token = get_required_secret("BOT_TOKEN")
DATABASE_URL = get_required_secret("DATABASE_URL")
debug = True if os.getenv("DEBUG", "True").lower() == "true" else False
