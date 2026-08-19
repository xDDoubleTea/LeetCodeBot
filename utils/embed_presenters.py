import logging
from typing import Set, List
import re2
from markdownify import MarkdownConverter
import discord
from discord import Client, Embed
from discord.ext import commands
from config.constants import PREVIEW_LEN

from db.problem import Problem, TopicTags
from models.leetcode import ProblemDifficulity, UserInfo
from utils.embed_utils import create_themed_embed

logger = logging.getLogger(__name__)


class LeetCodeMarkdownConverter(MarkdownConverter):
    """markdownify strips <sup>/<sub> content instead of marking it, so
    exponents like <sup>5</sup> collapse into surrounding text."""

    def convert_sup(self, el, text, parent_tags):
        if not text:
            return text
        return f"^{text}" if " " not in text else f"^({text})"

    def convert_sub(self, el, text, parent_tags):
        if not text:
            return text
        # escaped underscore so it can't pair with another literal "_"
        # elsewhere in the description and get parsed as italics
        return f"\\_{text}" if " " not in text else f"\\_({text})"


def _markdownify(html: str, **options) -> str:
    return LeetCodeMarkdownConverter(**options).convert(html)


def _fix_truncated_markdown(text: str) -> str:
    # drop a dangling 1-2 backtick remnant left at the cut point
    text = re2.sub(r"`{1,2}$", "", text)

    # odd number of complete ``` fences => still inside a code block
    if len(re2.findall(r"```", text)) % 2 != 0:
        if not text.endswith("\n"):
            text += "\n"
        return text + "```"

    if text.count("`") % 2 != 0:
        text += "`"
    if text.count("**") % 2 != 0:
        text += "**"
    elif re2.sub(r"\*\*", "", text).count("*") % 2 != 0:
        text += "*"

    return text


def parse_problem_desc(content: str) -> str:
    logger.debug("Parsing problem description")
    if not content:
        return "No description available."

    content = re2.sub(
        r"(?s)<table.*?>.*?</table>", "\n<em>[Table omitted for preview]<em>\n", content
    )

    md_text = _markdownify(content, heading_style="ATX", strip=["img"]).strip()
    md_text = re2.sub(r"\n\s*\n", "\n\n", md_text)

    if len(md_text) <= PREVIEW_LEN:
        return md_text

    truncated = md_text[:PREVIEW_LEN].rsplit(" ", 1)[0]
    truncated = _fix_truncated_markdown(truncated)

    return truncated + ("\n..." if truncated.endswith("```") else "...")


def get_difficulty_str_repr(difficulty_db_repr: int) -> str:
    """
    Converts the difficulty into human readable strings
    """
    try:
        difficulty = ProblemDifficulity.from_db_repr(difficulty_db_repr)
        return difficulty.str_repr
    except Exception:
        return "Unknown"


def get_user_info_embed(
    username: str, info: UserInfo, bot: commands.Bot | Client
) -> Embed:
    """
    Returns the embed for leetcode user.
    """
    embed = create_themed_embed(title=f"LeetCode User: {username}", client=bot)
    embed.url = f"https://leetcode.com/u/{username}/"
    third_party_links = [info.github_url, info.twitter_url, info.linkedin_url]
    value = "\n".join(link for link in third_party_links if link)
    ac_submission = info.ac_submission
    if ac_submission and ac_submission.difficulity.lower() == "all":
        embed.add_field(
            name="AC Submissions",
            value=f"Difficulty : All\nSovled: {ac_submission.ac_submission_count}\nTotal submitted and AC: {ac_submission.total_submissions_and_ac_count}",
            inline=False,
        )

    embed.add_field(name="Other Links", value=value, inline=False)
    profile = info.user_profile
    assert profile
    embed.set_thumbnail(url=profile.user_avatar)
    embed.add_field(name="Country", value=profile.country_name, inline=True)
    embed.description = f"User's About me: {profile.about_me}"

    company = profile.company
    job_title = profile.job_title
    school = profile.school
    if company:
        value = company
        if job_title:
            value = company + "\nJob Title: " + job_title
        embed.add_field(name="Company", value=value, inline=False)
    if school:
        embed.add_field(name="School", value=school, inline=True)

    websites = profile.websites
    if websites:
        embed.add_field(name="Websites", value="\n".join(websites), inline=False)
    return embed


def get_embed_color(difficulty_db_repr: int) -> discord.Color:
    try:
        # logger.debug(f"Getting embed color for difficulty {difficulty_db_repr}")
        difficulty = ProblemDifficulity.from_db_repr(difficulty_db_repr)
        return difficulty.embed_color
    except Exception:
        return discord.Color.blue()  # Default to blue if unknown


def get_problem_desc_pictures(content: str) -> List[str]:
    if not content:
        return []

    matches = re2.findall(r'<img[^>]+src="([^">]+)"', content)
    return matches[:4]


def get_problem_desc_embed(
    problem: Problem, problem_tags: Set[TopicTags], bot: commands.Bot | Client
) -> List[Embed]:
    """
    Get the description embed for a given problem.
    """
    embed = create_themed_embed(
        title=f"{problem.problem_frontend_id}. {problem.title}",
        client=bot,
        description=parse_problem_desc(problem.description),
    )
    embed.url = problem.url
    difficulty_str = get_difficulty_str_repr(problem.difficulty)
    embed.add_field(name="Difficulty", value=difficulty_str, inline=True)
    embed.add_field(
        name="Tags",
        value=f"||{', '.join(map(lambda tag: tag.tag_name, problem_tags))}||"
        if len(problem_tags) != 0
        else "No tags available",
        inline=True,
    )
    embed.color = get_embed_color(problem.difficulty)

    embeds = [embed]
    image_urls = get_problem_desc_pictures(content=problem.description)

    if image_urls:
        embed.set_image(url=image_urls[0])

        for img_url in image_urls[1:]:
            img_embed = discord.Embed(url=problem.url)
            img_embed.set_image(url=img_url)
            embeds.append(img_embed)

    return embeds
