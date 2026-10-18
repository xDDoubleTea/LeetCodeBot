# Main Feature

## LeetCode Commands

For available commands, please refer to [README](https://github.com/xDDoubleTea/LeetCodeBot/blob/main/README.md).

### The Shared Workflow

The three commands that open a thread directly — `/problem`, `/daily` and `/random` — are wrapped in the `handle_leetcode_interaction` decorator from `utils/handle_leetcode_interation.py`. The decorated method's only job is to return a `ProblemWithTags`; the decorator does the rest:

1. Defers the interaction, since fetching can outrun Discord's three-second window.
2. Calls the command body to resolve the problem.
3. Replies and stops if nothing came back.
4. Hands the problem to `ProblemThreadsManager.reopen_or_create_problem_thread`.
5. Replies with a link, saying whether the thread was created or already existed.
6. Turns `ForumChannelNotFound`, `FetchError` and `ProblemNotFound` into readable messages.

This is why the individual commands are only a few lines each. `/problem-title` and `/filter-by-tag` do not use it: they return several candidates, so they answer with a paginated selection view from `view/pagination_view.py` instead.

### LeetCode Problem Thread Creation

**`/problem <id>`** opens a discussion thread for a problem by its LeetCode number.

Logic flow:

1. User invokes `/problem <id>`.
2. `LeetCodeProblemManager.get_problem_with_frontend_id` resolves it: the in-memory cache first, then the database, then LeetCode. A problem fetched from LeetCode is stored and cached, so later lookups do not fetch it again. If LeetCode has no problem with that id, it raises `ProblemNotFound`. See [Where Problem Data Comes From](#where-problem-data-comes-from).
3. `reopen_or_create_problem_thread` looks up the guild's configured forum channel, raising `ForumChannelNotFound` if `/set_forum_channel` was never run.
4. It checks the database for an existing thread for that problem in that guild.
5. If one exists and is still present in Discord, it is reused. If the record exists but the thread is gone, the record is deleted and a new thread is created.
6. `_create_thread` builds the thread: title `"<id>. <title>"`, the problem URL, the description embed, and the forum tags `LeetCode` plus the difficulty — creating those tags in the channel if they are missing.
7. The new thread is recorded in the database and the user gets a link.

Involved files:

- `cogs/leetcode.py` — `leetcode_problem`, the command definition.
- `utils/handle_leetcode_interation.py` — `handle_leetcode_interaction`, the shared workflow above.
- `core/leetcode_problem.py` — `get_problem_with_frontend_id`, `get_problem_from_db`, `add_problem_to_db`.
- `core/leetcode_api.py` — `fetch_problem_by_frontend_id`.
- `core/problem_threads.py` — `reopen_or_create_problem_thread`, `get_forum_channel`, `get_thread_by_problem_id`, `_create_thread`, `create_thread_in_db`, `delete_thread_from_db`.
- `utils/embed_presenters.py` — `get_problem_desc_embed`.
- `utils/discord_utils.py` — `try_get_channel`.
- `db/problem.py`, `db/problem_threads.py`, `db/thread_channel.py` — the models.

```mermaid
flowchart TD
    Start([User invokes /problem ID]) --> Defer[Decorator defers interaction]
    Defer --> CheckCache{In problem cache?}

    CheckCache -- Yes --> Resolved[ProblemWithTags]
    CheckCache -- No --> CheckDB{In database?}
    CheckDB -- Yes --> Resolved
    CheckDB -- No --> FetchAPI{On LeetCode?}
    FetchAPI -- Yes --> Store[Store in database and cache] --> Resolved
    FetchAPI -- No --> NotFound[ProblemNotFound -> error message]

    Resolved --> Forum{Forum channel set?}
    Forum -- No --> NoForum[ForumChannelNotFound -> error message]
    Forum -- Yes --> Existing{Thread record exists?}

    Existing -- No --> Create[Create thread, record it]
    Existing -- Yes --> Alive{Thread still in Discord?}
    Alive -- Yes --> Reuse[Reuse existing thread]
    Alive -- No --> Purge[Delete stale record] --> Create

    Create --> Confirm[Reply with link]
    Reuse --> Confirm
    Confirm --> End([End])
    NotFound --> End
    NoForum --> End
```

### Daily Challenge Thread Creation

**`/daily`** does the same thing for today's LeetCode challenge. Only step 2 differs: the daily problem is not addressable by id, so it comes from the API.

1. `LeetCodeProblemManager.get_daily_problem` returns the cached daily problem if one is held.
2. Otherwise `fetch_daily_problem` calls `LeetCodeAPI.fetch_daily`, parsed by `_parse_daily_problem_response`.
3. The result is reconciled against the problem cache and the database, so the daily thread refers to the same `Problem` row as `/problem <id>` would.
4. From there the shared workflow takes over, identically.

Involved files, in addition to those above:

- `core/leetcode_api.py` — `fetch_daily`, `_parse_daily_problem_response`, `_validate_response`.
- `core/leetcode_problem.py` — `get_daily_problem`, `fetch_daily_problem`.
- `graphql/fetch_daily.graphql` — the query itself.

```mermaid
flowchart TD
    Start([User invokes /daily]) --> Defer[Decorator defers interaction]
    Defer --> Cached{Daily problem cached?}

    Cached -- Yes --> Resolved[ProblemWithTags]
    Cached -- No --> FetchAPI[fetch_daily from LeetCode API]
    FetchAPI --> Reconcile[Reconcile with cache and database]
    Reconcile --> Resolved

    Resolved --> Shared[Shared thread workflow]
    Shared --> Confirm[Reply with link]
    Confirm --> End([End])
```

### Where Problem Data Comes From

`refresh_cache` loads the full problem list:

- A `tasks.loop` in `cogs/leetcode.py` runs it daily at `LEETCODE_API_REFRESH_TIME` (`config/constants.py`).
- `/refresh` runs it on request, for the bot owner (`DEV_ID`) only.

It calls `LeetCodeAPI.fetch_all_problems`, upserts the results into the database, and rebuilds the in-memory cache.

A problem added to LeetCode since the last refresh is fetched on its first lookup. `LeetCodeAPI.fetch_problem_by_frontend_id` searches the problem list by the id, keeps the result whose frontend id matches exactly, and returns `None` when there is none. One lookup costs one request.

### Activity Records

`ActivityManager` (`core/activity.py`) stores two tables as data for the planned `/suggest` ranking (#86):

- `problem_opens`: a row each time a user opens or reopens a problem thread through `/problem`, `/daily`, `/random`, or the select menu of `/filter-by-tag` and `/problem-title`, with the command name and the interaction's timestamp.
- `thread_solutions`: a row for each message with a fenced code block posted in a problem thread, with the fence's language and the message's timestamp. A message is recorded once, keyed by its id. The code stays in Discord.

Both timestamps come from Discord and are stored as UTC without a timezone.

Recording is best-effort: a database error is logged and the command or message carries on.

## UML charts

Generated by `scripts/generate_uml.sh`. Select a chart to open it full size.

### Packages

Imports between `main`, the cogs, `core` and `db`.

[![UML packages chart](../assets/packages.svg)](../assets/packages.svg)

### Classes

`LeetCodeBot` and the managers in `core`, and how they reference each other.

[![UML classes chart](../assets/classes.svg)](../assets/classes.svg)

Each module's classes with their attributes and methods:

#### `LeetCodeBot`

[![main classes chart](../assets/classes_main.svg)](../assets/classes_main.svg)

#### `core/activity.py`

[![activity classes chart](../assets/classes_activity.svg)](../assets/classes_activity.svg)

#### `core/leetcode_api.py`

[![leetcode_api classes chart](../assets/classes_leetcode_api.svg)](../assets/classes_leetcode_api.svg)

#### `core/leetcode_dc_link.py`

[![leetcode_dc_link classes chart](../assets/classes_leetcode_dc_link.svg)](../assets/classes_leetcode_dc_link.svg)

#### `core/leetcode_problem.py`

[![leetcode_problem classes chart](../assets/classes_leetcode_problem.svg)](../assets/classes_leetcode_problem.svg)

#### `core/problem_threads.py`

[![problem_threads classes chart](../assets/classes_problem_threads.svg)](../assets/classes_problem_threads.svg)

### Database models

Tables and their foreign keys. `?` marks a nullable column.

[![Database tables and foreign keys](../assets/models.svg)](../assets/models.svg)
