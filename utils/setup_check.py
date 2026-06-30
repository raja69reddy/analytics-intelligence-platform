"""Verify required packages are importable. Run after pip install -r requirements.txt."""
import sys

sys.stdout.reconfigure(encoding="utf-8")

PACKAGES = [
    ("pandas",     "pandas"),
    ("sqlalchemy", "sqlalchemy"),
    ("psycopg2",   "psycopg2-binary"),
    ("streamlit",  "streamlit"),
    ("plotly",     "plotly"),
    ("dotenv",     "python-dotenv"),
]


def check():
    failed = []
    for module, pkg in PACKAGES:
        try:
            __import__(module)
        except ImportError:
            failed.append(pkg)

    if failed:
        print(f"❌ Missing packages: {', '.join(failed)}")
        print("Run: pip install -r requirements.txt")
        sys.exit(1)
    else:
        print("✅ All packages OK")


if __name__ == "__main__":
    check()
