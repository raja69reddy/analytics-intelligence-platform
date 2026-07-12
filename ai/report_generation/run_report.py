"""CLI pipeline: generate a full AI analytics report and save to disk.

Usage:
    python ai/report_generation/run_report.py
"""

import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def main():
    from ai.report_generation.generator import ReportGenerator
    from ai.report_generation.formatter import save_report, format_as_markdown

    print("=" * 60)
    print("Analytics Intelligence Platform — AI Report Generator")
    print("=" * 60)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    start = time.time()

    try:
        generator = ReportGenerator()
        print("Loading data from PostgreSQL views...")
        print("Generating AI report sections (this may take 30-60 seconds)...")
        report = generator.generate_full_report()
    except EnvironmentError as exc:
        print(f"\nConfiguration error: {exc}")
        print("Add OPENAI_API_KEY to your .env file to generate AI reports.")
        sys.exit(1)
    except RuntimeError as exc:
        print(f"\nAPI error: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"\nUnexpected error: {exc}")
        sys.exit(1)

    elapsed = round(time.time() - start, 1)

    # Save to disk
    path = save_report(report)
    print(f"\nReport saved to: {path}")
    print(f"Generation time: {elapsed}s")
    print()

    # Print first 15 lines to console
    md = format_as_markdown(report)
    lines = md.splitlines()
    print("--- Report Preview (first 15 lines) ---")
    for line in lines[:15]:
        print(line)
    if len(lines) > 15:
        print(f"... ({len(lines) - 15} more lines in saved file)")

    print()
    print("=" * 60)
    print("Sections generated:")
    for section in ("traffic", "behavior", "conversions", "seo", "executive_summary"):
        status = "✅" if report.get(section) else "❌"
        print(f"  {status} {section}")
    print("=" * 60)


if __name__ == "__main__":
    main()
