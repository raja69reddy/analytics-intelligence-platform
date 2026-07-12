"""Verify all packages from requirements.txt are importable."""

import sys

sys.stdout.reconfigure(encoding="utf-8")

PACKAGES = [
    # Core
    ("psycopg2", "psycopg2-binary"),
    ("sqlalchemy", "sqlalchemy"),
    ("pandas", "pandas"),
    ("dotenv", "python-dotenv"),
    ("numpy", "numpy"),
    # Dashboard
    ("streamlit", "streamlit"),
    ("plotly", "plotly"),
    ("altair", "altair"),
    # Ingestion / HTTP
    ("requests", "requests"),
    ("bs4", "beautifulsoup4"),
    ("user_agents", "user-agents"),
    # Utilities
    ("tqdm", "tqdm"),
    ("click", "click"),
    ("dateutil", "python-dateutil"),
    ("faker", "Faker"),
]


def check() -> bool:
    """Check every required package and return True if all pass."""
    failed = []
    for module, pkg in PACKAGES:
        try:
            __import__(module)
        except ImportError:
            failed.append(pkg)

    if failed:
        print(f"❌ Missing packages: {', '.join(failed)}")
        print("Run: pip install -r requirements.txt")
        return False

    print(f"✅ All packages OK ({len(PACKAGES)} checked)")
    return True


if __name__ == "__main__":
    ok = check()
    sys.exit(0 if ok else 1)
