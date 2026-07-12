"""Natural Language Query (NLQ) module.

Converts plain-English analytics questions into SQL using the OpenAI API,
executes them against PostgreSQL, and returns structured results.

Public exports:
    NLQEngine  — main class: translate, validate, execute, format
    run_nlq    — convenience function for the CLI pipeline
"""

from ai.nlq.nlq_engine import NLQEngine
from ai.nlq.run_nlq import run_nlq

__all__ = ["NLQEngine", "run_nlq"]
