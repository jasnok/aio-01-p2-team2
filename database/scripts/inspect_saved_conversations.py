"""Read-only catalog/count inspection; never prints DSNs, credentials or row content."""
import json
import os
from pathlib import Path

import psycopg
from dotenv import dotenv_values
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[2]
TABLES = ['users', 'saved_conversations', 'saved_messages', 'saved_message_sources']


def main():
    configs = {}
    for name in ('backend', 'database', 'legal_mcp'):
        values = {**dotenv_values(ROOT / '.env'), **dotenv_values(ROOT / name / '.env')}
        dsn = os.environ.get('DATABASE_URL') or values.get('DATABASE_URL')
        if not dsn:
            print(json.dumps({'config': name, 'error': 'DATABASE_URL absent; no fallback used'}))
            continue
        dsn = dsn.replace('postgresql+psycopg://', 'postgresql://')
        configs.setdefault(dsn, []).append(name)
    for dsn, names in configs.items():
        try:
            with psycopg.connect(dsn, connect_timeout=5, row_factory=dict_row,
                                 options='-c default_transaction_read_only=on -c statement_timeout=15000') as conn:
                with conn.transaction():
                    conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
                    result = {'configs': names}
                    result['server'] = conn.execute('SELECT current_database() AS database, version() AS version').fetchone()
                    result['columns'] = conn.execute('''SELECT table_name, column_name, data_type,
                        udt_name, is_nullable, column_default FROM information_schema.columns
                        WHERE table_schema='public' AND table_name=ANY(%s)
                        ORDER BY table_name, ordinal_position''', (TABLES,)).fetchall()
                    result['constraints'] = conn.execute('''SELECT c.conrelid::regclass::text AS table_name,
                        c.conname, c.convalidated, pg_get_constraintdef(c.oid) AS definition
                        FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid
                        JOIN pg_namespace n ON n.oid=t.relnamespace
                        WHERE n.nspname='public' AND t.relname=ANY(%s) ORDER BY 1,2''', (TABLES,)).fetchall()
                    result['indexes'] = conn.execute('''SELECT tablename, indexname, indexdef
                        FROM pg_indexes WHERE schemaname='public' AND tablename=ANY(%s)
                        ORDER BY 1,2''', (TABLES,)).fetchall()
                    result['counts'] = {}
                    for table in TABLES:
                        if conn.execute('SELECT to_regclass(%s) AS t', ('public.' + table,)).fetchone()['t']:
                            result['counts'][table] = conn.execute(
                                psycopg.sql.SQL('SELECT count(*) AS count FROM public.{}').format(
                                    psycopg.sql.Identifier(table))).fetchone()['count']
                    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
        except Exception as exc:
            # Exception text can contain connection credentials; report only class/SQLSTATE.
            print(json.dumps({'configs': names, 'error': type(exc).__name__,
                              'sqlstate': getattr(exc, 'sqlstate', None)}))
            raise SystemExit(1) from None


if __name__ == '__main__':
    main()
