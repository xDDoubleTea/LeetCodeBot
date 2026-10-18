import pytest

from utils.code_blocks import code_block_languages


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("```py\nprint(1)\n```", ["py"]),
        ("```Python\nprint(1)```", ["python"]),
        ("```c++\nint x;\n```", ["c++"]),
        ("```\nplain\n```", [None]),
        ("here:\n```cpp\na\n```\nand\n```py\nb\n```", ["cpp", "py"]),
    ],
)
def test_fenced_blocks_give_their_languages(content, expected):
    assert code_block_languages(content) == expected


@pytest.mark.parametrize(
    "content",
    [
        "how do I start this?",
        "use `dp[i]` here",
        "```inline```",
        "```py\nnever closed",
    ],
)
def test_no_fenced_block_gives_an_empty_list(content):
    assert code_block_languages(content) == []
