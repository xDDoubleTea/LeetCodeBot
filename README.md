# LeetCode Discord Bot

## How to run this bot

### Prerequisites

Ensure [git](https://git-scm.com/install/), [uv](https://docs.astral.sh/uv/getting-started/installation/), [python](https://www.python.org/downloads/) are installed on your system.

### Run these commands in your terminal

```bash
git clone https://github.com/xDDoubleTea/LeetCodeBot
cd LeetCodeBot
uv run main.py
```

### Visual studio code

If you prefer GUI and you use vscode, you can use the built-in `Clone repository` function to clone this repository. Also make sure to run `uv sync` for code completions to work properly in vscode!!!

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

- python
- discord.py
- sqlalchemy
- sqlite
