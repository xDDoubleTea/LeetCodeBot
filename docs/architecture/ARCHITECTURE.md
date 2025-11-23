# Developer Documentation & Architecture

<!--toc:start-->

- [Developer Documentation & Architecture](#developer-documentation-architecture)
  - [1. System Overview](#1-system-overview)
  - [2. Directory Structure](#2-directory-structure)
  - [3. Main Logic Flow](#3-main-logic-flow)
    - [Startup Sequence](#startup-sequence)
    - [LeetCode Commands](#leetcode-commands)
  - [4. Development Setup](#4-development-setup)
  <!--toc:end-->

## 1. System Overview

**LeetCodeBot** is a Python-based Discord bot designed to make discussion for LeetCode problems easier in discord. It uses `discord.py` (or similar) and organizes features into modular extensions ("cogs").

## 2. Directory Structure

- **`main.py`**: The entry point. Initializes the bot, loads environment variables, and starts the event loop.
- **`core/`**: Contains the core bot logic, likely including the custom Bot class subclass and global error handling.
- **`cogs/`**: Modular features. Each file here represents a specific category of commands (e.g., `leetcode.py`, `admin.py`).
- **`db/`**: Database interactions and ORM models.
- **`models`**: Data models representing entities. E.g., ProblemDifficulty.
- **`utils/`**: Helper functions used across multiple cogs.
- **`.env.example`**: Template for environment variables.
- **`config/`**: Configuration files for different environments (development, production).

## 3. Main Logic Flow

### Startup Sequence

1. `config/secrets.py` loads variables from `.env`.
2. The Bot instance created in `main.py`.
3. Extensions from `cogs/` are loaded when the bot instance is initializing.
4. The classes in `core/` are setup, including cache loading.

### LeetCode Commands

See [Main Features](./main-feature.md)

## 4. Development Setup

1. Install dependencies: `uv sync`.
2. Setup variables: Copy `.env.example` to `.env`.
3. Run the bot: `python main.py`.
