from dotenv import load_dotenv

load_dotenv()


def get_required_secret(key: str) -> str:
    import os

    value = os.getenv(key)
    if value is None:
        raise EnvironmentError(
            f"Required secret '{key}' is not set in environment variables."
        )
    return value


bot_token = get_required_secret("BOT_TOKEN")
DATABASE_URL = get_required_secret("DATABASE_URL")
