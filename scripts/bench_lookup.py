"""
Measure problem-lookup latency outside Discord.

Runs two samples against the real `LeetCodeProblemManager`:

Warm
    Problems already present locally, looked up through
    `get_problem_with_frontend_id`. The production database is opened read-only
    and its rows are loaded into the manager's cache, so the sample measures the
    path a command takes on a cache hit.

Cold
    Problems fetched over LeetCode's GraphQL API, parsed by `LeetCodeAPI`,
    written with `add_problem_to_db` and then looked up. These writes go to a
    throwaway in-memory database, and the title slugs they need are read from
    the read-only production database, so neither the deployed cache nor its
    file is touched. A sleep between requests keeps the API happy.

Usage:

    uv run python scripts/bench_lookup.py
    uv run python scripts/bench_lookup.py --warm-n 200 --cold-n 30 --cold-sleep 1.5
"""

import argparse
import asyncio
import logging
import os
import random
import statistics
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

import aiohttp
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.leetcode_api import LeetCodeAPI
from core.leetcode_problem import LeetCodeProblemManager
from db.async_db_manager import AsyncDatabaseManager
from db.base import Base
from models.leetcode import ProblemWithTags

logger = logging.getLogger("bench_lookup")

DEFAULT_WARM_N = 120
DEFAULT_COLD_N = 25
DEFAULT_COLD_SLEEP = 1.0
SAMPLE_SEED = 20261002


def read_only_url(database_url: str) -> str:
    """
    The same SQLite database as `database_url`, opened read-only.

    SQLite refuses every write on a `mode=ro` connection, which is what keeps a
    benchmark run from touching the deployed cache.
    """
    path = urlsplit(database_url).path.lstrip("/")
    if not path:
        raise ValueError(f"{database_url} names no database file")
    return f"sqlite+aiosqlite:///file:{path}?mode=ro&uri=true"


def title_slug(url: str) -> str:
    """The LeetCode title slug a problem URL ends with."""
    return urlsplit(url).path.strip("/").removeprefix("problems/")


def percentile(values: list[float], fraction: float) -> float:
    """The nearest-rank percentile of `values`."""
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round(fraction * len(ordered)) - 1))
    return ordered[index]


def report(label: str, samples: list[float]) -> None:
    if not samples:
        print(f"{label:<5} n=0     no samples")
        return
    print(
        f"{label:<5} n={len(samples):<5} "
        f"median={statistics.median(samples):>10.3f} ms  "
        f"p95={percentile(samples, 0.95):>10.3f} ms"
    )


async def fetch_problem_over_graphql(api: LeetCodeAPI, slug: str) -> ProblemWithTags:
    """
    One problem, straight from LeetCode's GraphQL API.

    Uses the client's own `fetch_problem_by_id` query and response parser, and
    fills in the URL the parser expects, which this query does not return.
    """
    response = await api.session.post(
        url=api._leetcode_graphql_url,
        headers=api._leetcode_headers,
        json={
            "query": api.queries["fetch_problem_by_id"],
            "variables": {"titleSlug": slug},
        },
    )
    payload = await api._validate_response(response, f"Failed to fetch problem {slug}")
    raw_problem = payload["data"]["question"]
    raw_problem["url"] = f"https://leetcode.com/problems/{slug}"
    return await api._parse_single_problem_response(raw_problem)


async def warm_sample(
    manager: LeetCodeProblemManager, problem_frontend_ids: list[int]
) -> list[float]:
    """Time `get_problem_with_frontend_id` for problems held in the cache."""
    samples: list[float] = []
    for problem_frontend_id in problem_frontend_ids:
        started = time.perf_counter()
        await manager.get_problem_with_frontend_id(
            problem_frontend_id=problem_frontend_id
        )
        samples.append((time.perf_counter() - started) * 1000)
    return samples


async def cold_sample(
    manager: LeetCodeProblemManager,
    api: LeetCodeAPI,
    slugs: list[str],
    sleep_seconds: float,
) -> list[float]:
    """
    Time the full miss path: GraphQL fetch, parse, persist, then look up.

    The manager must start with an empty cache and an empty database for the
    lookup at the end to be a real one.
    """
    samples: list[float] = []
    for index, slug in enumerate(slugs):
        if index:
            await asyncio.sleep(sleep_seconds)

        started = time.perf_counter()
        try:
            problem_with_tags = await fetch_problem_over_graphql(api, slug)
            stored = await manager.add_problem_to_db(
                problem_with_tags.problem, problem_with_tags.tags
            )
            await manager.get_problem_with_frontend_id(
                problem_frontend_id=stored.problem_frontend_id
            )
        except Exception as e:
            logger.warning("Skipping %s: %s", slug, e)
            continue
        samples.append((time.perf_counter() - started) * 1000)
    return samples


async def run(warm_n: int, cold_n: int, cold_sleep: float) -> None:
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise OSError("DATABASE_URL is not set; the warm run needs the real database")

    rng = random.Random(SAMPLE_SEED)

    live_engine = create_async_engine(read_only_url(database_url))
    cold_engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with cold_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with aiohttp.ClientSession() as session:
        api = LeetCodeAPI(session=session)
        api._load_graphql_queries()

        live_manager = LeetCodeProblemManager(
            leetcode_api=api,
            async_database_manager=AsyncDatabaseManager(SimpleNamespace(), live_engine),
        )
        cold_manager = LeetCodeProblemManager(
            leetcode_api=api,
            async_database_manager=AsyncDatabaseManager(SimpleNamespace(), cold_engine),
        )

        try:
            problems = await live_manager.get_problems_from_db()
            if len(problems) < warm_n:
                raise OSError(
                    f"The database holds {len(problems)} problems, "
                    f"fewer than the {warm_n} the warm run asks for"
                )
            live_manager.all_problem_cache = {
                problem.problem_frontend_id: problem for problem in problems
            }
            live_manager.free_problem_cache = {
                problem.problem_frontend_id: problem
                for problem in problems
                if not problem.premium
            }

            warm_ids = rng.sample(sorted(live_manager.all_problem_cache), warm_n)
            warm = await warm_sample(live_manager, warm_ids)

            free_rows = [problem for problem in problems if not problem.premium]
            slugs = [
                title_slug(problem.url) for problem in rng.sample(free_rows, cold_n)
            ]
            cold = await cold_sample(cold_manager, api, slugs, cold_sleep)
        finally:
            await live_engine.dispose()
            await cold_engine.dispose()

    print()
    report("warm", warm)
    report("cold", cold)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--warm-n", type=int, default=DEFAULT_WARM_N)
    parser.add_argument("--cold-n", type=int, default=DEFAULT_COLD_N)
    parser.add_argument("--cold-sleep", type=float, default=DEFAULT_COLD_SLEEP)
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    asyncio.run(run(args.warm_n, args.cold_n, args.cold_sleep))


if __name__ == "__main__":
    main()
