"""Run once to create all tables, then apply all views."""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.db import run_sql_file  # noqa: E402

SQL_DIR = os.path.dirname(__file__)
VIEWS_DIR = os.path.join(SQL_DIR, "views")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--views-only", action="store_true")
    args = parser.parse_args()

    if not args.views_only:
        print("Applying schema.sql …")
        run_sql_file(os.path.join(SQL_DIR, "schema.sql"))
        print("  done.")

    for fname in sorted(os.listdir(VIEWS_DIR)):
        if fname.endswith(".sql"):
            print(f"Applying view {fname} …")
            run_sql_file(os.path.join(VIEWS_DIR, fname))
            print("  done.")

    print("All done.")


if __name__ == "__main__":
    main()
