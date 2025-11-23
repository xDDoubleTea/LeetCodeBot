# Development Guide

<!--toc:start-->

- [Development Guide](#development-guide)
  - [Setting Up Your Development Environment](#setting-up-your-development-environment)
    - [Creating a Discord Bot](#creating-a-discord-bot)
    - [Configuring the Bot](#configuring-the-bot)
  - [Running the Bot Locally](#running-the-bot-locally)
  - [Testing](#testing)
  - [VSCode Setup](#vscode-setup)
  <!--toc:end-->

<!-- omit in toc -->

## Setting Up Your Development Environment

This project uses [uv](https://github.com/astral-sh/uv) as the python package manager. Make sure it is installed.

This project uses [Rapptz/discord.py: An API wrapper for Discord written in Python.](https://github.com/Rapptz/discord.py) for interacting with the Discord API.

To set up your development environment, run the following command to install the required dependencies:

```bash
uv sync
source ./venv/bin/activate
```

Copy `.env.example` to `.env`, and fill the BOT_TOKEN with your discord bot token.

### Creating a Discord Bot

There are tons of tutorials online on how to create a discord bot and get its token, here is a quick one:

[Creating a Discord Bot in Python - GeeksforGeeks](https://www.geeksforgeeks.org/python/discord-bot-in-python/)

TL;DR: Go to discord developer portal, create a new application, add a bot to it, copy the token and invite the bot to your server.

### Configuring the Bot

Take a look at `config/constants.py`, you can change the command prefix, the guild id for testing, and your discord user id for owner-only commands.

You can, of course, add more configurations as needed.

## Running the Bot Locally

With the development environment set up, you can run the bot locally using the following command:

```bash
bin/start.bash # If you use bash
bin/start.zsh # If you use zsh
```

Alternatively, you can run the bot directly using `uv`:

```bash
uv run main.py
```

## Testing

Currently, there are no automated tests set up for this project. Testing is done manually by running the bot and verifying its functionality.

If you would like to contribute tests, please consider using a testing framework like `unittest` or `pytest` and follow the project's coding style.

## VSCode Setup

Chances are you are using VSCode as your IDE. After running `uv sync`, you can open the project in VSCode and it should automatically detect the virtual environment located at `./venv`. If not, you can manually select the interpreter by pressing `Ctrl+Shift+P` and searching for `Python: Select Interpreter`, then choosing the one located at `./venv/bin/python`.

> I don't use VSCode myself, so if you are using another IDE and would like to contribute setup instructions for it, please feel free to open a PR!

## Architecture Overview

Please refer to the [Architecture Documentation](/docs/architecture/ARCHITECTURE.md).
