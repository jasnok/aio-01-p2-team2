"""Compare saved context reads on synthetic PostgreSQL temporary tables only."""
import argparse
import asyncio
import hashlib
import json
import os
import statistics
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter

import asyncpg

from backend.app.repositories import saved_conversation_repository as repository_module
from backend.app.services.saved_conversation_service import SavedConversationService


async def create_tables(connection):
    await connection.execute("SET search_path TO pg_temp")
    await connection.execute("""
        CREATE TEMP TABLE saved_conversations (
            id INT PRIMARY KEY, user_id INT, title TEXT, category TEXT, save_state TEXT,
            saved_at TIMESTAMPTZ, created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ);
        CREATE TEMP TABLE saved_messages (
            id INT PRIMARY KEY, conversation_id INT, role TEXT, content TEXT,
            execution_key TEXT, processing_status TEXT, snapshot JSONB, created_at TIMESTAMPTZ);
        CREATE INDEX ON saved_messages(conversation_id, id DESC);
        CREATE INDEX ON saved_messages(conversation_id, id) WHERE role='user';
        INSERT INTO saved_conversations VALUES
            (1,42,'synthetic','legal_terms','selected',NOW(),NOW(),NOW());
    """)


def repository_for_connection(connection):
    class Pool:
        @asynccontextmanager
        async def acquire(self):
            yield connection
    async def pool():
        return Pool()
    return pool


async def benchmark(url, counts, repeats):
    connection = await asyncpg.connect(url)
    original_pool = repository_module.get_db_pool
    try:
        await create_tables(connection)
        repository_module.get_db_pool = repository_for_connection(connection)
        repository = repository_module.SavedConversationRepository()
        results = []
        for count in counts:
            await connection.execute("TRUNCATE saved_messages")
            await connection.execute("""
                INSERT INTO saved_messages
                SELECT i,1,CASE WHEN i%2=1 THEN 'user' ELSE 'assistant' END,
                       'synthetic-'||i,i::text,'completed',
                       jsonb_build_object('payload',repeat('x',1024)),NOW()
                FROM generate_series(1,$1::int) i
            """, count)
            await connection.execute("ANALYZE saved_messages")
            methods = {"full": repository.restore, "bounded": repository.restore_context}
            samples = {name: [] for name in methods}
            restored = {}
            for method in methods.values():
                await method(42, 1)  # Warm each query once; no cold-cache claim.
            for iteration in range(repeats):
                order = list(methods) if iteration % 2 == 0 else list(reversed(methods))
                for name in order:
                    start = perf_counter()
                    restored[name] = await methods[name](42, 1)
                    samples[name].append(round((perf_counter() - start) * 1000, 4))
            contexts = [SavedConversationService._context_from_messages(value["messages"], 3000)
                        for value in restored.values()]
            assert contexts[0] == contexts[1]
            results.append({"message_count": count, "context_equal": True,
                "variants": {name: {
                    "returned_rows": len(restored[name]["messages"]),
                    "serialized_bytes": len(json.dumps(restored[name], default=str).encode()),
                    "median_ms": statistics.median(values), "samples_ms": values,
                } for name, values in samples.items()}})
        return {"scope": "synthetic local PostgreSQL; warm alternating reads; excludes LLM/API",
                "postgres_version": await connection.fetchval("SHOW server_version"),
                "repeats": repeats, "snapshot_payload_bytes": 1024,
                "repository_sha256": hashlib.sha256(Path(repository_module.__file__).read_bytes()).hexdigest(),
                "results": results}
    finally:
        repository_module.get_db_pool = original_pool
        await connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=20)
    args = parser.parse_args()
    if not os.environ.get("RUN_POSTGRES_INTEGRATION") or args.repeats < 1:
        parser.error("Set RUN_POSTGRES_INTEGRATION and use a positive repeat count")
    report = asyncio.run(benchmark(os.environ["RUN_POSTGRES_INTEGRATION"], [10, 1000, 10000], args.repeats))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
