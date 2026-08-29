# LeetCode Discord Bot

![LeetCode](https://img.shields.io/badge/LeetCode-%23000000.svg?style=for-the-badge&logo=LeetCode&logoColor=#d16c06)
![tests](https://github.com/xDDoubleTea/LeetCodeBot/actions/workflows/pytest.yml/badge.svg)
![docs deploy](https://github.com/xDDoubleTea/LeetCodeBot/actions/workflows/docs.yml/badge.svg)

## AI assistant

![Claude](https://img.shields.io/badge/claude-%23D97757.svg?style=for-the-badge&logo=claude&logoColor=white)
![Claude Code](https://img.shields.io/badge/Claude%20Code-%23D97757.svg?style=for-the-badge&logo=claudecode&logoColor=white)
![Google Gemini](https://img.shields.io/badge/google%20gemini-%238E75B2.svg?style=for-the-badge&logo=google%20gemini&logoColor=white)

![OpenCode](https://img.shields.io/badge/opencode-%23000000.svg?style=for-the-badge&logo=opencode&logoColor=ffffff)
![Ollama](https://img.shields.io/badge/ollama-%23000000.svg?style=for-the-badge&logo=ollama&logoColor=white)

## Features

- Discuss LeetCode problems with friends in your Discord server.
- Get problem details, solutions, and hints directly in chat.
- Track your LeetCode progress and share achievements.
- Supports daily challenges.

## Usage

| Command                                           | Description                                                              | Admin Only |
| ------------------------------------------------- | ------------------------------------------------------------------------ | ---------- |
| `/help`                                           | Gets help about the bot's commands.                                      | No         |
| `/daily`                                          | Gets today's LeetCode problem.                                           | No         |
| `/problem [id]`                                   | Gets a LeetCode problem by its ID.                                       | No         |
| `/problem-title <title>`                          | Gets a LeetCode problem by matching its title with regex.                | No         |
| `/problem-list <name>`                            | Creates a list of problems associated with user. Does nothing right now. | No         |
| `/random`                                         | Gets a random LeetCode problem.                                          | No         |
| `/recent-submissions <leetcode_username> [limit]` | Gets a user's recent submissions.                                        | No         |
| `/filter-by-tag <tag_name>`                       | Get a list of LeetCode problem that contains the given tag               | No         |
| `/desc [id]`                                      | Gets a LeetCode problem description by its ID.                           | No         |
| `/migrate`                                        | Migrates from the old threads.                                           | No         |
| `/set_forum_channel`                              | Sets the forum channel for problems.                                     | Yes        |
| `/refresh`                                        | Refreshes the LeetCode problems cache.                                   | Yes        |
| `/ping`                                           | Checks the bot's latency.                                                | No         |
| `/is-leetcode-down`                               | Checks the LeetCode API status.                                          | No         |
| `/check-available-tags`                           | Get all possible tags for a LeetCode problem.                            | No         |
| `/statistics [username]`                          | Gets user statistics by LeetCode username.                               | No         |

## How to run this bot

### Prerequisites

Ensure [git](https://git-scm.com/install/), [uv](https://docs.astral.sh/uv/getting-started/installation/), [python](https://www.python.org/downloads/) are installed on your system.

### Run these commands in your terminal

```bash
git clone https://github.com/xDDoubleTea/LeetCodeBot
cd LeetCodeBot
cp .env.example .env    # then fill in BOT_TOKEN
uv run main.py
```

The bot creates the database and applies any outstanding migrations on startup, so a
fresh clone needs no separate database setup.

If you already have a `db/*.db` from before alembic was adopted, run
`uv run alembic stamp head` once before starting the bot. See
[the database guide](docs/database.md) for schema changes and the alembic commands.

### Visual studio code

If you prefer GUI and you use vscode, you can use the built-in `Clone repository` function to clone this repository.
Make sure to first run `uv sync` to generate the virtual environment for vscode to automatically detect.

## Roadmap

- [x] Get problem details by ID and create a thread in discord
- [x] Get daily challenge problem and create a thread in discord
- [x] Get problem details by title slug and create a thread in discord
- [x] Get user statistics
- [ ] Per guild leaderboards
- [ ] Documentation
- [ ] Probably submit directly from discord?
- [ ] Migrate to postgresql probably

## Tech Stack

![Python](https://img.shields.io/badge/python-%233670A0.svg?style=for-the-badge&logo=python&logoColor=ffdd54)
![SQLAlchemy](https://img.shields.io/badge/sqlalchemy-%23D71F00.svg?style=for-the-badge&logo=sqlalchemy&logoColor=white)
![SQLite](https://img.shields.io/badge/sqlite-%2307405e.svg?style=for-the-badge&logo=sqlite&logoColor=white)

[Rapptz/discord.py: An API wrapper for Discord written in Python.](https://github.com/Rapptz/discord.py)
