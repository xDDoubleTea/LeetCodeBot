#!/usr/bin/env bash
# Regenerate the charts in docs/assets/. Needs graphviz (`dot`).
#
#   scripts/generate_uml.sh
#
# packages.svg  imports between main, cogs, core and db (pyreverse)
# classes.svg   LeetCodeBot and the core managers, names only (pyreverse)
# classes_<module>.svg
#               one module's classes with their members (pyreverse)
# models.svg    database tables and foreign keys (scripts/er_diagram.py)
set -euo pipefail

cd "$(dirname "$0")/.."
out=docs/assets
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

pyreverse() {
    uv run --with pylint pyreverse --colorized --output svg --output-directory "$tmp" "$@" >/dev/null
}

pyreverse --project bot main cogs core db
mv "$tmp/packages_bot.svg" "$out/packages.svg"

pyreverse --only-classnames --project core main core
mv "$tmp/classes_core.svg" "$out/classes.svg"

for module in main core.activity core.leetcode_api core.leetcode_dc_link \
    core.leetcode_problem core.problem_threads; do
    uv run --with pylint pyreverse --colorized --output dot --output-directory "$tmp" \
        --project "$module" "$module" >/dev/null
    uv run python -m scripts.wrap_signatures <"$tmp/classes_$module.dot" |
        dot -Tsvg -o "$out/classes_${module#core.}.svg"
done

uv run python -m scripts.er_diagram | dot -Tsvg -o "$out/models.svg"
