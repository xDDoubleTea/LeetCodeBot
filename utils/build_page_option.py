from discord import SelectOption

from db.problem import Problem
from models.leetcode import ProblemDifficulity


def build_problem_options(cur_page_problem: list[Problem]) -> list[SelectOption]:
    return [
        SelectOption(
            label=f"{p.problem_frontend_id}. {p.title} [{ProblemDifficulity.from_db_repr(p.difficulty).value[1]}]"[
                :100
            ],
            value=str(p.problem_frontend_id),
        )
        for p in cur_page_problem
    ]
