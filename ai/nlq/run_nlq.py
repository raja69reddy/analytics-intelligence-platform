"""CLI interface for the NLQ engine.

Usage:
    python ai/nlq/run_nlq.py "What are the top 5 channels by sessions?"
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def run_nlq(question: str) -> dict:
    """Run a question through the NLQ engine and return the result dict."""
    from ai.nlq.nlq_engine import NLQEngine

    engine = NLQEngine()
    return engine.ask(question)


def main():
    if len(sys.argv) < 2:
        print('Usage: python ai/nlq/run_nlq.py "<question>"')
        print(
            'Example: python ai/nlq/run_nlq.py "What are the top 5 channels by sessions?"'
        )
        sys.exit(1)

    question = " ".join(sys.argv[1:])
    print(f"\nQuestion: {question}")
    print("=" * 60)

    result = run_nlq(question)

    print("\nGenerated SQL:")
    print("-" * 40)
    if result["sql"]:
        print(result["sql"])
    else:
        print("(no SQL generated)")

    print("\nResults:")
    print("-" * 40)
    if result["data"] is not None and not result["data"].empty:
        print(result["data"].to_string(index=False))
    elif result["error"]:
        print(f"Error: {result['error']}")
    else:
        print("No results returned.")

    cache_note = " (from cache)" if result["from_cache"] else ""
    print(f"\nExecution time: {result['execution_time_s']}s{cache_note}")


if __name__ == "__main__":
    main()
