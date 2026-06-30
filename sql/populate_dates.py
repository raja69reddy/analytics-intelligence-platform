"""Fill dim_dates with every date from 2023-01-01 to 2025-12-31."""
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import text

from utils.db import get_engine

START = date(2023, 1, 1)
END = date(2025, 12, 31)


def build_row(d: date) -> dict:
    return {
        "date_id":        int(d.strftime("%Y%m%d")),
        "full_date":      d,
        "day_of_week":    d.isoweekday(),
        "day_name":       d.strftime("%A"),
        "week_number":    int(d.strftime("%V")),
        "month":          d.month,
        "month_name":     d.strftime("%B"),
        "quarter":        (d.month - 1) // 3 + 1,
        "year":           d.year,
        "is_weekend":     d.isoweekday() >= 6,
        "is_month_start": d.day == 1,
        "is_month_end":   (d + timedelta(days=1)).month != d.month,
    }


def populate(start: date = START, end: date = END) -> int:
    engine = get_engine()
    inserted = 0
    current = start
    with engine.begin() as conn:
        while current <= end:
            row = build_row(current)
            result = conn.execute(
                text("""
                    INSERT INTO dim_dates
                        (date_id, full_date, day_of_week, day_name, week,
                         month, month_name, quarter, year, is_weekend,
                         is_month_start, is_month_end)
                    VALUES
                        (:date_id, :full_date, :day_of_week, :day_name, :week_number,
                         :month, :month_name, :quarter, :year, :is_weekend,
                         :is_month_start, :is_month_end)
                    ON CONFLICT (date_id) DO NOTHING
                """),
                row,
            )
            inserted += result.rowcount
            current += timedelta(days=1)
    return inserted


if __name__ == "__main__":
    print(f"Populating dim_dates from {START} to {END} ...")
    n = populate()
    total = (END - START).days + 1
    print(f"  Inserted {n} rows  ({total - n} already existed)")
    print("Done.")
