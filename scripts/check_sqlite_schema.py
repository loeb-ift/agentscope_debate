#!/usr/bin/env python3
import argparse
import sqlite3
from typing import List, Tuple

EXPECTED = {
    "tools": [
        "id", "name", "description", "group", "provider", "version",
        "json_schema", "openapi_spec", "created_at",
    ],
    "evidence_docs": [
        "id", "debate_id", "title", "source", "snippet", "fulltext_ref",
        "artifact_type", "timestamp", "tool", "citations", "provenance",
    ],
    "debate_configs": [
        "id", "topic", "chairman_id", "rounds", "enable_cross_examination", "created_at"
    ],
    "checkpoints": [
        "id", "debate_id", "plan_node_id", "context_snapshot", "cited_evidence_ids",
        "lease_token", "lease_expiry", "created_at"
    ],
}


def get_table_info(cur, table: str) -> List[Tuple]:
    try:
        cur.execute(f"PRAGMA table_info('{table}')")
        return cur.fetchall()
    except sqlite3.OperationalError:
        return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db-path", default="test.db", help="Path to sqlite db (default: test.db)")
    args = ap.parse_args()

    print(f"[i] Checking sqlite schema at: {args.db_path}")
    try:
        conn = sqlite3.connect(args.db_path)
    except sqlite3.Error as e:
        print(f"[!] Cannot open DB: {e}")
        return 2

    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in cur.fetchall()}
    print(f"[i] Tables found: {len(tables)}")

    exit_code = 0
    for table, cols in EXPECTED.items():
        print(f"\n=== {table} ===")
        if table not in tables:
            print(f"[!] Missing table: {table}")
            exit_code = 1
            continue
        info = get_table_info(cur, table)
        existing = [row[1] for row in info]
        missing = [c for c in cols if c not in existing]
        print(f"Columns: {existing}")
        if missing:
            print(f"[!] Missing columns: {missing}")
            exit_code = 1
        else:
            print(f"[OK] Required columns present")

    conn.close()
    if exit_code == 0:
        print("\n[OK] SQLite schema looks compatible with project expectations.")
    else:
        print("\n[!] SQLite schema has differences. Consider migration or ALTER TABLE.")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
