"""ReportGenerator — uses OpenAI to generate analytics executive reports."""

import os
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv

load_dotenv()


class ReportGenerator:
    """Generates AI-written analytics reports from PostgreSQL view data."""

    def __init__(self, model: str = "gpt-3.5-turbo"):
        self.model = model
        self._client = None

    @property
    def client(self):
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

    # ── internal helper ───────────────────────────────────────────────────────

    def _call_api(self, prompt: str, max_tokens: int = 600) -> str:
        """Send a prompt to OpenAI and return the text response."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        except EnvironmentError:
            raise
        except Exception as exc:
            raise RuntimeError(f"OpenAI API error: {exc}") from exc

    @staticmethod
    def _df_summary(df: pd.DataFrame, max_rows: int = 15) -> str:
        """Convert a DataFrame to a compact text summary for the prompt."""
        if df is None or df.empty:
            return "(no data available)"
        return df.head(max_rows).to_string(index=False)

    # ── public section generators ─────────────────────────────────────────────

    def generate_traffic_report(self, df: pd.DataFrame) -> str:
        """Write a 3-paragraph executive summary of traffic trends."""
        from ai.report_generation.prompts import TRAFFIC_REPORT_PROMPT

        prompt = TRAFFIC_REPORT_PROMPT.format(data=self._df_summary(df))
        return self._call_api(prompt)

    def generate_behavior_report(self, df: pd.DataFrame) -> str:
        """Write a 3-paragraph summary of user behavior patterns."""
        from ai.report_generation.prompts import BEHAVIOR_REPORT_PROMPT

        prompt = BEHAVIOR_REPORT_PROMPT.format(data=self._df_summary(df))
        return self._call_api(prompt)

    def generate_conversion_report(self, df: pd.DataFrame) -> str:
        """Write a 3-paragraph summary of conversion and revenue performance."""
        from ai.report_generation.prompts import CONVERSION_REPORT_PROMPT

        prompt = CONVERSION_REPORT_PROMPT.format(data=self._df_summary(df))
        return self._call_api(prompt)

    def generate_seo_report(self, df: pd.DataFrame) -> str:
        """Write a 3-paragraph summary of SEO and content health."""
        from ai.report_generation.prompts import SEO_REPORT_PROMPT

        prompt = SEO_REPORT_PROMPT.format(data=self._df_summary(df))
        return self._call_api(prompt)

    def generate_full_report(self) -> dict:
        """Load data from all views, generate all 4 sections, and add an executive summary.

        Returns a report dict with keys:
            traffic, behavior, conversions, seo,
            executive_summary, generated_at
        """
        from utils.db import query_df
        from ai.report_generation.prompts import EXECUTIVE_SUMMARY_PROMPT

        # ── load data ─────────────────────────────────────────────────────────
        traffic_df = query_df(
            "SELECT * FROM vw_daily_traffic ORDER BY session_date DESC LIMIT 30"
        )
        channel_df = query_df(
            "SELECT * FROM vw_channel_performance ORDER BY total_sessions DESC"
        )
        behavior_df = query_df(
            "SELECT * FROM vw_top_pages ORDER BY total_requests DESC LIMIT 20"
        )
        scroll_df = query_df("SELECT * FROM vw_scroll_depth")
        conversion_df = query_df(
            "SELECT channel_grouping, "
            "SUM(sessions) AS sessions, "
            "SUM(conversions) AS conversions, "
            "ROUND(SUM(conversions)::NUMERIC / NULLIF(SUM(sessions),0)*100,2) AS cvr_pct, "
            "SUM(revenue) AS revenue "
            "FROM raw_ga4_sessions "
            "GROUP BY channel_grouping ORDER BY revenue DESC"
        )
        seo_df = query_df("SELECT * FROM vw_seo ORDER BY word_count DESC LIMIT 20")

        # Combine traffic and channel for the traffic section
        combined_traffic = pd.concat(
            [
                traffic_df.assign(_section="daily"),
                channel_df.assign(_section="channel"),
            ],
            ignore_index=True,
        )

        # ── generate sections ─────────────────────────────────────────────────
        sections = {
            "traffic": self.generate_traffic_report(combined_traffic),
            "behavior": self.generate_behavior_report(
                pd.concat([behavior_df, scroll_df], ignore_index=True)
            ),
            "conversions": self.generate_conversion_report(conversion_df),
            "seo": self.generate_seo_report(seo_df),
        }

        # ── executive summary ─────────────────────────────────────────────────
        sections_text = "\n\n".join(
            f"### {k.title()}\n{v}" for k, v in sections.items()
        )
        exec_summary = self._call_api(
            EXECUTIVE_SUMMARY_PROMPT.format(sections=sections_text),
            max_tokens=400,
        )

        return {
            **sections,
            "executive_summary": exec_summary,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
