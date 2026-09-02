import logging
import logging.handlers
import os
import sys

from config.constants import BOT_LOG_FILE_NAME, LOG_DIR, SQLALCHEMY_LOG_FILE_NAME


def setup_logger(log_level: int = logging.INFO):
    log_dir = LOG_DIR
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(
        "[{asctime}] [{levelname:<8}] {name}: {message}",
        datefmt=datefmt,
        style="{",
    )

    console_handler = logging.StreamHandler(sys.stdout)

    main_file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=os.path.join(log_dir, BOT_LOG_FILE_NAME),
        when="midnight",
        interval=1,
        backupCount=7,
        encoding="utf-8",
    )

    logging.basicConfig(level=log_level, handlers=[console_handler, main_file_handler])

    noisy_loggers = ["discord", "discord.http", "discord.gateway", "urllib3", "asyncio"]
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.INFO)

    console_handler.setFormatter(formatter)
    main_file_handler.setFormatter(formatter)

    db_logger = logging.getLogger("sqlalchemy.engine")
    db_logger.setLevel(logging.WARNING)
    db_file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=os.path.join(log_dir, SQLALCHEMY_LOG_FILE_NAME),
        when="midnight",
        interval=1,
        backupCount=7,
        encoding="utf-8",
    )
    db_logger.propagate = False
    db_file_handler.setFormatter(formatter)

    db_logger.addHandler(db_file_handler)
    db_logger.addHandler(console_handler)
