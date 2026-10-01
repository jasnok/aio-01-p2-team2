"""Measure history summary projection on isolated synthetic PostgreSQL data."""
import argparse
import ast
import asyncio
import hashlib
import inspect
import json
import os
import re
import statistics
import textwrap
from functools import lru_cache
from pathlib import Path
from time import perf_counter

import asyncpg

from backend.app.repositories import saved_conversation_repository as module
from backend.app.services.saved_conversation_service import SavedConversationService
from scripts.benchmark_saved_context import create_tables, repository_for_connection


@lru_cache(maxsize=1)
def baseline_query():
    """Reconstruct the preceding query by changing only snapshot projection."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(module.SavedConversationRepository.list_history_page)))
    query = next(node.value for node in ast.walk(tree) if isinstance(node, ast.Constant)
                 and isinstance(node.value, str) and "FROM saved_conversations c" in node.value)
    query, replacements = re.subn(
        r"jsonb_build_object\('payload', jsonb_build_object\([\s\S]*?\)\) AS assistant_snapshot",
        "last_answer.snapshot AS assistant_snapshot", query)
    assert replacements == 1, "History projection changed; update the benchmark baseline"
    return query


async def full_snapshot_page(connection, user_id=42, page=1, page_size=20):
    total = await connection.fetchval("SELECT COUNT(*) FROM saved_conversations WHERE user_id=$1", user_id)
    rows = await connection.fetch(baseline_query(), user_id, page_size, (page - 1) * page_size)
    return [dict(row) for row in rows], int(total)


async def benchmark(url, repeats):
    connection = await asyncpg.connect(url)
    original_pool = module.get_db_pool
    try:
        await create_tables(connection)
        await connection.execute("CREATE INDEX ON saved_conversations(user_id, updated_at DESC, id DESC)")
        module.get_db_pool = repository_for_connection(connection)
        repository = module.SavedConversationRepository()
        results = []
        for count in (10, 1000):
            await connection.execute("TRUNCATE saved_messages, saved_conversations")
            await connection.execute("""
                INSERT INTO saved_conversations
                SELECT i,42,'synthetic-'||i,'housing','selected',NOW(),NOW(),NOW()
                FROM generate_series(1,$1::int) i;
            """, count)
            await connection.execute("""
                INSERT INTO saved_messages
                SELECT i*2-1,i,'user','synthetic question-'||i,i::text,'completed',NULL,NOW()
                FROM generate_series(1,$1::int) i;
            """, count)
            await connection.execute("""
                INSERT INTO saved_messages
                SELECT i*2,i,'assistant','synthetic answer-'||i,i::text,'completed',
                    jsonb_build_object('version',1,'payload',jsonb_build_object(
                        'question_summary','synthetic summary-'||i,'answer','synthetic answer-'||i,
                        'unused_evidence',repeat('x',65536))),NOW()
                FROM generate_series(1,$1::int) i;
            """, count)
            await connection.execute("ANALYZE saved_messages; ANALYZE saved_conversations")
            async def full():
                return await full_snapshot_page(connection)
            async def projected():
                return await repository.list_history_page(user_id=42, page=1, page_size=20)
            methods = {"full": full, "projected": projected}
            samples = {name: [] for name in methods}
            pages = {}
            for method in methods.values():
                await method()
            for iteration in range(repeats):
                order = list(methods) if iteration % 2 == 0 else list(reversed(methods))
                for name in order:
                    start = perf_counter()
                    pages[name] = await methods[name]()
                    samples[name].append(round((perf_counter() - start) * 1000, 4))
            public = {name: [SavedConversationService._history_item(row) for row in page[0]]
                      for name, page in pages.items()}
            assert public["full"] == public["projected"]
            assert pages["full"][1] == pages["projected"][1] == count
            results.append({"conversation_count": count, "public_equal": True,
                "public_serialized_bytes": len(json.dumps(public["projected"], default=str).encode()),
                "variants": {name: {"returned_rows": len(pages[name][0]),
                    "serialized_bytes": len(json.dumps(pages[name][0], default=str).encode()),
                    "median_ms": statistics.median(values), "samples_ms": values}
                    for name, values in samples.items()}})
        return {"scope": "synthetic local PostgreSQL; warm alternating page reads; excludes LLM/API/serialization",
                "postgres_version": await connection.fetchval("SHOW server_version"),
                "repeats": repeats, "page_size": 20, "unused_payload_bytes": 65536,
                "repository_sha256": hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest(),
                "baseline_query_sha256": hashlib.sha256(baseline_query().encode()).hexdigest(),
                "results": results}
    finally:
        module.get_db_pool = original_pool
        await connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=20)
    args = parser.parse_args()
    if not os.environ.get("RUN_POSTGRES_INTEGRATION") or args.repeats < 1:
        parser.error("Set RUN_POSTGRES_INTEGRATION and use a positive repeat count")
    report = asyncio.run(benchmark(os.environ["RUN_POSTGRES_INTEGRATION"], args.repeats))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
