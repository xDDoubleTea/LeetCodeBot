from discord import Client
from discord.ext.commands import Bot
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker


class DatabaseManager:
    def __init__(self, bot: Bot | Client, engine: Engine):
        self.bot = bot
        self.engine = engine
        self.session = None

    def __enter__(self):
        """Returns a database session"""
        try:
            Session = sessionmaker(
                bind=self.engine, autoflush=True, expire_on_commit=False
            )
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
            if exc_type:
                print(f"Exception {exc_val}. Rolling back...")
                self.session.rollback()
            else:
                self.session.commit()
            self.session.close()
        except AssertionError:
            print("Database connection or cursor was not initialized correctly.")
            return True
        finally:
            return False
