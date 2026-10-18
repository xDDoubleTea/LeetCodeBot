"""
Print a graphviz entity-relationship diagram of the database models to stdout.

Each table lists its columns with their types; edges are foreign keys. Run by
`scripts/generate_uml.sh`, which renders it to `docs/assets/models.svg`.
"""

import html

import db.activity
import db.leetcode_dc_link
import db.problem
import db.problem_threads
import db.thread_channel  # noqa: F401
from db.base import Base

HEADER_COLOR = "#7aaadc"


def column_row(column) -> str:
    flags = []
    if column.primary_key:
        flags.append("PK")
    if column.foreign_keys:
        flags.append("FK")
    if column.unique:
        flags.append("UQ")
    type_name = html.escape(str(column.type))
    if column.nullable and not column.primary_key:
        type_name += "?"
    return (
        f'<tr><td align="left" port="{column.name}_in">{column.name}</td>'
        f'<td align="left">{type_name}</td>'
        f'<td align="left" port="{column.name}_out">{" ".join(flags)}</td></tr>'
    )


def table_node(table) -> str:
    rows = "".join(column_row(column) for column in table.columns)
    return (
        f'  "{table.name}" [label=<<table border="0" cellborder="1" cellspacing="0" cellpadding="4">'
        f'<tr><td colspan="3" bgcolor="{HEADER_COLOR}"><b>{table.name}</b></td></tr>'
        f"{rows}</table>>];"
    )


def main() -> None:
    lines = [
        "digraph models {",
        "  rankdir=LR;",
        '  node [shape=plaintext, fontname="Helvetica"];',
        '  edge [arrowhead=crow, arrowtail=none, dir=both, color="#555555"];',
    ]
    tables = sorted(Base.metadata.tables.values(), key=lambda t: t.name)
    lines += [table_node(table) for table in tables]
    for table in tables:
        for fk in table.foreign_keys:
            target = fk.column
            lines.append(
                f'  "{target.table.name}":"{target.name}_out":e -> '
                f'"{table.name}":"{fk.parent.name}_in":w;'
            )
    lines.append("}")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
