# LeetCode Discord Bot

## Features

- Discuss LeetCode problems with friends in your Discord server.
- Get problem details, solutions, and hints directly in chat.
- Track your LeetCode progress and share achievements.
- Supports daily challenges.

## Usage

| Command             | Description                                         |
| ------------------- | --------------------------------------------------- |
| `/help`             | Gets help about the bot's commands.                 |
| `/daily`            | Gets today's LeetCode problem.                      |
| `/problem [id]`     | Gets a LeetCode problem by its ID.                  |
| `/desc [id]`        | Gets a LeetCode problem description by its ID.      |
| `/migrate`          | Migrates from the old threads.                      |
| `/set_forum_channel`  | Sets the forum channel for problems.                |
| `/refresh`          | Refreshes the LeetCode problems cache.              |
| `/ping`             | Checks the bot's latency.                           |
| `/check_leetcode_api` | Checks the LeetCode API status.                     |

## Roadmap

- [x] Get problem details by ID and create a thread in discord
- [x] Get daily challenge problem and create a thread in discord
- [ ] Get problem details by title slug and create a thread in discord
- [ ] Chinese support
- [ ] Get user statistics
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
