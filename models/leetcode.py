from enum import Enum
import discord


class ProblemDifficulity(Enum):
    EASY = (0, "Easy", discord.Color.green())
    MEDIUM = (1, "Medium", discord.Color.orange())
    HARD = (2, "Hard", discord.Color.red())

    def __init__(self, db_repr: int, str_repr: str, embed_color: discord.Color) -> None:
        self.db_repr = db_repr
        self.str_repr = str_repr
        self.embed_color = embed_color

    @classmethod
    def from_db_repr(cls, db_repr: int) -> "ProblemDifficulity":
        for difficulty in ProblemDifficulity:
            if difficulty.db_repr == db_repr:
                return difficulty
        raise ValueError(f"No matching difficulty for db_repr: {db_repr}")

    @classmethod
    def from_str_repr(cls, str_repr: str) -> "ProblemDifficulity":
        for difficulty in ProblemDifficulity:
            if difficulty.str_repr.lower() == str_repr.lower():
                return difficulty
        raise ValueError(f"No matching difficulty for str_repr: {str_repr}")
