# LeetCode Discord Bot

## Features

- Discuss LeetCode problems with friends in your Discord server.
- Get problem details, solutions, and hints directly in chat.
- Track your LeetCode progress and share achievements.
- Supports daily challenges.

## Usage

| Command                  | Description                                    | Admin Only |
| ------------------------ | ---------------------------------------------- | ---------- |
| `/help`                  | Gets help about the bot's commands.            | No         |
| `/daily`                 | Gets today's LeetCode problem.                 | No         |
| `/problem [id]`          | Gets a LeetCode problem by its ID.             | No         |
| `/desc [id]`             | Gets a LeetCode problem description by its ID. | No         |
| `/migrate`               | Migrates from the old threads.                 | No         |
| `/set_forum_channel`     | Sets the forum channel for problems.           | Yes        |
| `/refresh`               | Refreshes the LeetCode problems cache.         | Yes        |
| `/ping`                  | Checks the bot's latency.                      | No         |
| `/check_leetcode_api`    | Checks the LeetCode API status.                | No         |
| `/statistics [username]` | Gets user statistics by LeetCode username.     | No         |

## Roadmap

- [x] Get problem details by ID and create a thread in discord
- [x] Get daily challenge problem and create a thread in discord
- [ ] Get problem details by title slug and create a thread in discord
- [ ] Chinese support
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

- [noworneverev/leetcode-api: LeetCode API - LeetCode questions sorted by likes - Daily updated LeetCode database](https://github.com/noworneverev/leetcode-api/tree/main)
