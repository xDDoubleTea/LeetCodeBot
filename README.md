# Discord bot template

## Features

- Using `uv` as the python virtual environment manager, written in `rust`!
- Using `discord.py` as the discord bot framework
- Using `sqlalchemy` for ORM database

## Setup

```bash
git clone https://github.com/xDDoubleTea/Dc-py-bot-tmpl
cd Dc-py-bot-tmpl
uv sync

# Unix like
source .venv/bin/activate
# If you are on windows:
source .\.venv\bin\activate.bat

# Remember to copy the .env.example to .env and fill in your bot token and the database url

uv run main.py
```
