#!/usr/bin/env python3
import os
import sys
import argparse
import psycopg
from psycopg.rows import tuple_row

# Load environment variables from a .env file in the current working directory
# (e.g., C:\APP\DEV\backend\.env) so DATABASE_URL is available to this script.
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    # If python-dotenv isn't installed, the script will still work
    # if DATABASE_URL is already present in the environment.
    pass

def get_conn():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg.connect(url)

def main():
    parser = argparse.ArgumentParser(description="Run a SQL query against DATABASE_URL")
    parser.add_argument("-q", "--query", required=True, help="SQL to execute")
    args = parser.parse_args()

    sql = args.query
    with get_conn() as conn:
        with conn.cursor(row_factory=tuple_row) as cur:
            cur.execute(sql)
            try:
                rows = cur.fetchall()
            except psycopg.ProgrammingError:
                rows = None
        conn.commit()

    if rows is not None:
        for r in rows:
            print("\t".join("" if v is None else str(v) for v in r))

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
