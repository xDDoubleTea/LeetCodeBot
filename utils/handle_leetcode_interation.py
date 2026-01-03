import functools
from discord import Interaction, Thread
from discord.channel import ThreadWithMessage
from models.leetcode import ThreadCreationEnum
from utils.custom_exceptions import ForumChannelNotFound
from core.leetcode_api import FetchError
from db.problem import Problem
from main import logger


def handle_leetcode_interaction(is_daily: bool = False):
    """
    Decorator to handle the common workflow for LeetCode problem commands:
    1. Defer interaction.
    2. Execute the decorated fetch function.
    3. Handle errors (Not Found, FetchError, etc.).
    4. Create/Reopen thread.
    5. Send success response.
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, interaction: Interaction, *args, **kwargs):
            await interaction.response.defer(thinking=True)
            try:
                assert interaction.guild

                # Execute the specific fetching logic defined in the command
                # The decorated function must return the 'problem' dictionary or None
                problem = await func(self, interaction, *args, **kwargs)

                if not problem:
                    if is_daily:
                        await interaction.followup.send(
                            "Daily problem not found. Check the leetcode api by /check_leetcode_api."
                        )
                    else:
                        # Attempt to retrieve ID for a better error message if available
                        problem_id = kwargs.get("id")
                        if problem_id:
                            await interaction.followup.send(
                                f"Problem with ID {problem_id} not found."
                            )
                        else:
                            await interaction.followup.send("Problem not found.")
                    return

                # Common Thread Management Logic
                (
                    thread,
                    thread_creation_enum,
                ) = await self.problem_threads_manager.reopen_or_create_problem_thread(
                    problem=problem,
                    guild=interaction.guild,
                    bot=self.bot,
                    is_daily=is_daily,
                )

                problem_obj = problem["problem"]
                assert isinstance(problem_obj, Problem)

                # Construct Success Message
                if is_daily:
                    if thread_creation_enum == ThreadCreationEnum.CREATE:
                        assert isinstance(thread, ThreadWithMessage)
                        msg = f"Created thread for today's problem in {thread.thread.mention}"
                    else:
                        assert isinstance(thread, Thread)
                        msg = f"Thread for today's problem already exists: {thread.mention}"
                else:
                    # Add extra context for random problems if difficulty was specified
                    extra_info = ""
                    difficulty = kwargs.get("difficulty")
                    if difficulty:
                        extra_info = f" with difficulty {difficulty}"

                    if thread_creation_enum == ThreadCreationEnum.CREATE:
                        assert isinstance(thread, ThreadWithMessage)
                        msg = f"Created thread for problem {problem_obj.problem_frontend_id} in {thread.thread.mention}{extra_info}"
                    else:
                        assert isinstance(thread, Thread)
                        msg = f"Thread for problem {problem_obj.problem_frontend_id} already exists: {thread.mention}"
                        await thread.send(
                            f"Thread already exists {interaction.user.mention}"
                        )

                await interaction.followup.send(msg)

            except ForumChannelNotFound as e:
                await interaction.followup.send(f"{e}")
            except FetchError as e:
                logger.error("FetchError occurred", exc_info=e)
                await interaction.followup.send(f"{e}")
            except Exception as e:
                logger.error("An error occurred", exc_info=e)
                await interaction.followup.send(
                    f"An error occurred while processing the request: {e}"
                )

        return wrapper

    return decorator
