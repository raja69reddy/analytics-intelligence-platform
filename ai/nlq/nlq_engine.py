"""NLQ Engine — converts plain-English questions to SQL using the OpenAI API."""

import os
import time
import pandas as pd
from dotenv import load_dotenv

load_dotenv()


class NLQEngine:
    """Translates natural language questions into SQL and executes them against PostgreSQL."""

    def __init__(self):
        self._client = None
        self._cache = None

    # ── lazy singletons ──────────────────────────────────────────────────────

    @property
    def client(self):
        """Return a shared OpenAI client, created on first use."""
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError:
                raise ImportError(
                    "openai package not installed. Run: pip install openai"
                )
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise EnvironmentError(
                    "OPENAI_API_KEY is not set. Add it to your .env file."
                )
            self._client = OpenAI(api_key=api_key)
        return self._client

    @property
    def cache(self):
        if self._cache is None:
            from ai.nlq.cache import QueryCache

            self._cache = QueryCache()
        return self._cache

    # ── public API ───────────────────────────────────────────────────────────

    def translate_to_sql(self, question: str) -> str:
        """Convert a plain-English question to a SQL SELECT statement via OpenAI.

        Checks the cache first; only calls the API on a cache miss.
        Strips markdown code fences from the response if present.
        """
        from ai.nlq.prompts import SQL_SYSTEM_PROMPT
        from ai.nlq.safety import sanitize_input

        question = sanitize_input(question)

        cached = self.cache.get_cached_query(question)
        if cached:
            return cached["sql"]

        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": SQL_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"Convert this question to SQL: {question}",
                    },
                ],
                temperature=0,
                max_tokens=500,
            )
            sql = response.choices[0].message.content.strip()
            # Remove markdown code fences if the model wrapped the query
            if sql.startswith("```"):
                lines = sql.splitlines()
                sql = "\n".join(lines[1:-1]).strip()
            return sql
        except EnvironmentError:
            raise
        except Exception as exc:
            raise RuntimeError(f"OpenAI API error: {exc}") from exc

    def validate_sql(self, sql: str) -> bool:
        """Return True if sql passes the safety check (SELECT-only, no dangerous keywords)."""
        from ai.nlq.safety import is_safe_query

        return is_safe_query(sql)

    def execute_query(self, sql: str) -> pd.DataFrame:
        """Run sql against the database and return the results as a DataFrame."""
        from utils.db import query_df

        return query_df(sql)

    def format_response(self, df: pd.DataFrame, question: str) -> str:
        """Format a DataFrame result as a readable plain-text table."""
        if df is None or df.empty:
            return f"No results found for: {question}"
        lines = [
            f"Results for: {question}",
            f"{len(df)} row(s) returned\n",
            df.to_string(index=False),
        ]
        return "\n".join(lines)

    def ask(self, question: str) -> dict:
        """Full pipeline: question → SQL → results → formatted response.

        Returns a dict with keys:
          question, sql, data (DataFrame), response (str),
          error (str|None), execution_time_s (float), from_cache (bool)
        """
        start = time.time()
        result = {
            "question": question,
            "sql": None,
            "data": None,
            "response": None,
            "error": None,
            "execution_time_s": None,
            "from_cache": False,
        }

        try:
            # ── cache hit ────────────────────────────────────────────────────
            cached = self.cache.get_cached_query(question)
            if cached:
                result["sql"] = cached["sql"]
                result["data"] = cached["result"]
                result["from_cache"] = True
                result["response"] = self.format_response(cached["result"], question)
                result["execution_time_s"] = round(time.time() - start, 3)
                return result

            # ── translate ────────────────────────────────────────────────────
            try:
                sql = self.translate_to_sql(question)
            except (EnvironmentError, RuntimeError):
                # Try cache as fallback when API is unavailable
                cached = self.cache.get_cached_query(question)
                if cached:
                    result["sql"] = cached["sql"]
                    result["data"] = cached["result"]
                    result["from_cache"] = True
                    result["response"] = self.format_response(
                        cached["result"], question
                    )
                    result["execution_time_s"] = round(time.time() - start, 3)
                    return result
                raise

            result["sql"] = sql

            # ── validate ─────────────────────────────────────────────────────
            if not self.validate_sql(sql):
                raise ValueError(
                    "Generated SQL failed the safety check — only SELECT queries are allowed."
                )

            # ── execute ──────────────────────────────────────────────────────
            df = self.execute_query(sql)

            if df is None or df.empty:
                result["response"] = (
                    f"The query ran successfully but returned no data for: {question}"
                )
            else:
                result["data"] = df
                result["response"] = self.format_response(df, question)

            # ── cache successful result ───────────────────────────────────────
            self.cache.cache_query(question, sql, df)

        except EnvironmentError as exc:
            result["error"] = str(exc)
            result["response"] = (
                f"Configuration error: {exc}\n"
                "Tip: add OPENAI_API_KEY=<your-key> to your .env file."
            )
        except ValueError as exc:
            result["error"] = str(exc)
            result["response"] = (
                f"Safety error: {exc}\n"
                "Only SELECT queries are allowed. Try rephrasing your question."
            )
        except RuntimeError as exc:
            result["error"] = str(exc)
            # Surface cached results if the API call failed mid-flight
            cached = self.cache.get_cached_query(question)
            if cached:
                result["sql"] = cached["sql"]
                result["data"] = cached["result"]
                result["from_cache"] = True
                result["response"] = self.format_response(cached["result"], question)
                result["error"] = None
            else:
                result["response"] = (
                    f"API error: {exc}\nNo cached result available for fallback."
                )
        except Exception as exc:
            error_type = type(exc).__name__
            # Give a friendlier message for common DB connectivity errors
            if "connection" in str(exc).lower() or "psycopg2" in error_type.lower():
                result["error"] = str(exc)
                result["response"] = (
                    "Database connection error — check that PostgreSQL is running "
                    "and your .env credentials are correct."
                )
            else:
                result["error"] = str(exc)
                result["response"] = f"Unexpected error ({error_type}): {exc}"

        result["execution_time_s"] = round(time.time() - start, 3)
        return result
