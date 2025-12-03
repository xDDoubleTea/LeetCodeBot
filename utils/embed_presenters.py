from discord import Client, Embed
from typing import Set
from discord.ext import commands
from utils.embed_utils import create_themed_embed
from models.leetcode import ProblemDifficulity
import discord
from db.problem import Problem, TopicTags
from main import logger


def get_difficulty_str_repr(difficulty_db_repr: int) -> str:
    """
    Converts the difficulty into human readable strings
    """
    try:
        difficulty = ProblemDifficulity.from_db_repr(difficulty_db_repr)
        return difficulty.str_repr
    except Exception:
        return "Unknown"


def get_user_info_embed(username: str, info: dict, bot: commands.Bot | Client) -> Embed:
    """
    Returns the embed for leetcode user.
    """
    embed = create_themed_embed(title=f"LeetCode User: {username}", client=bot)
    embed.url = f"https://leetcode.com/u/{username}/"
    third_party_links = ["githubUrl", "twitterUrl", "linkedinUrl"]
    value = "\n".join(
        map(
            str,
            filter(lambda t: t, [info.get(key) for key in third_party_links]),
        )
    )
    submissions = info.get("submitStats")
    assert submissions
    ac_submission = submissions.get("acSubmissionNum")
    if ac_submission:
        for sub in ac_submission:
            if sub.get("difficulty").lower() == "all":
                embed.add_field(
                    name="AC Submissions",
                    value=f"Difficulty : All\nSovled: {sub.get('count')}\nTotal submitted and AC: {sub.get('submissions')}",
                    inline=False,
                )
                break

    embed.add_field(name="Other Links", value=value, inline=False)
    profile = info.get("profile")
    assert profile
    embed.set_thumbnail(url=profile.get("userAvatar"))
    embed.add_field(name="Country", value=profile.get("countryName"), inline=True)
    embed.description = f"User's About me: {profile.get('aboutMe')}"
    company = profile.get("company", "")
    job_title = profile.get("jobTitle", "")
    school = profile.get("school", "")
    if company:
        value = company
        if job_title:
            value = company + "\nJob Title: " + job_title
        embed.add_field(name="Company", value=value, inline=False)
    if school:
        embed.add_field(name="School", value=school, inline=True)
    websites = profile.get("websites")
    if websites:
        embed.add_field(name="Websites", value="\n".join(websites), inline=False)
    return embed


def get_embed_color(difficulty_db_repr: int) -> discord.Color:
    try:
        logger.debug(f"Getting embed color for difficulty {difficulty_db_repr}")
        difficulty = ProblemDifficulity.from_db_repr(difficulty_db_repr)
        return difficulty.embed_color
    except Exception:
        return discord.Color.blue()  # Default to blue if unknown


def get_problem_desc_picture(self, problem: Problem) -> str:
    # TODO: Returns the example pictures of the problems.
    return ""


def get_problem_desc_embed(
    problem: Problem, problem_tags: Set[TopicTags], bot: commands.Bot | Client
) -> Embed:
    """
    Get the description embed for a given problem.
    """
    embed = create_themed_embed(
        title=f"{problem.problem_frontend_id}. {problem.title}",
        client=bot,
        description=problem.description,
    )
    embed.url = problem.url
    difficulty_str = get_difficulty_str_repr(problem.difficulty)
    embed.add_field(name="Difficulty", value=difficulty_str, inline=True)
    embed.add_field(
        name="Tags",
        value=", ".join(map(lambda tag: tag.tag_name, problem_tags)),
        inline=True,
    )
    embed.color = get_embed_color(problem.difficulty)
    return embed
