from discord import Client
from discord.ext.commands import Bot
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker
import logging


class DatabaseManager:
    def __init__(self, bot: Bot | Client, engine: Engine, logger: logging.Logger):
        self.bot = bot
        self.engine = engine
        self.session = None
        self.logger = logger

    def __enter__(self):
        """Returns a database session"""
        try:
            Session = sessionmaker(
                bind=self.engine, autoflush=True, expire_on_commit=False
            )
            self.logger.debug("Creating new database session...")
            self.session = Session()
            return self.session
        except Exception as e:
            print(f"Database connection error: {e}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Commits or rollback a session
        """
        try:
            assert self.session
            self.logger.debug("Closing database session...")
            if exc_type:
                self.logger.error(
                    f"Exception occurred: {exc_val}. Rolling back session...",
                    exc_info=exc_val,
                )
                self.session.rollback()
            else:
                self.session.commit()
            self.session.close()
        except AssertionError:
            self.logger.error("Database session was not initialized correctly.")
            return True
        finally:
            return False
