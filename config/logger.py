import logging
import logging.handlers
import os


def setup_logger(log_level: int = logging.INFO):
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    logger = logging.getLogger("LeetCodeBot")
    logger.setLevel(log_level)
    console_handler = logging.StreamHandler()

    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=os.path.join(log_dir, "bot.log"),
        when="midnight",
        interval=1,
        backupCount=7,
        encoding="utf-8",
    )
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(
        "[{asctime}] [{levelname:<8}] {name}: {message}",
        datefmt=datefmt,
        style="{",
    )
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    if not logger.hasHandlers():
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

    db_logger = logging.getLogger("sqlalchemy.engine")
    db_logger.setLevel(logging.WARNING)
    db_file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=os.path.join(log_dir, "sqlalchemy.log"),
        when="midnight",
        interval=1,
        backupCount=7,
        encoding="utf-8",
    )
    db_file_handler.setFormatter(formatter)
    if not db_logger.hasHandlers():
        db_logger.addHandler(db_file_handler)
