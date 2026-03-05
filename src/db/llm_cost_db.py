import sqlite3
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class LLMCostDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._initialize_db()

    def _initialize_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS llm_costs (
                    timestamp TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    prompt_tokens INTEGER NOT NULL,
                    completion_tokens INTEGER NOT NULL,
                    estimated_cost REAL NOT NULL
                )
            """)
            # Add columns for actual token tracking (idempotent)
            self._add_column_if_missing(cursor, "llm_costs", "actual_input_tokens", "INTEGER")
            self._add_column_if_missing(cursor, "llm_costs", "actual_output_tokens", "INTEGER")
            self._add_column_if_missing(cursor, "llm_costs", "cached_tokens", "INTEGER")
            self._add_column_if_missing(cursor, "llm_costs", "input_cost", "REAL")
            self._add_column_if_missing(cursor, "llm_costs", "output_cost", "REAL")

            # Add index for date queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_llm_costs_date
                ON llm_costs(substr(timestamp, 1, 10))
            """)
            conn.commit()

    def _add_column_if_missing(self, cursor, table: str, column: str, col_type: str):
        """Add a column to a table if it doesn't already exist."""
        try:
            cursor.execute(f"SELECT {column} FROM {table} LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")

    def add_log_entry(
        self,
        model_name: str,
        prompt_tokens: int,
        completion_tokens: int,
        estimated_cost: float,
        timestamp: datetime = None,
        actual_input_tokens: int = None,
        actual_output_tokens: int = None,
        cached_tokens: int = None,
        input_cost: float = None,
        output_cost: float = None,
    ):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                ts = (timestamp or datetime.now()).isoformat()
                cursor.execute(
                    """INSERT INTO llm_costs
                    (timestamp, model_name, prompt_tokens, completion_tokens,
                     estimated_cost, actual_input_tokens, actual_output_tokens,
                     cached_tokens, input_cost, output_cost)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (ts, model_name, prompt_tokens, completion_tokens,
                     estimated_cost, actual_input_tokens, actual_output_tokens,
                     cached_tokens, input_cost, output_cost)
                )
                conn.commit()
        except sqlite3.Error as e:
            logger.warning(f"Database error adding log entry: {e}")

    def get_daily_cost(self, date: datetime) -> float:
        date_str = date.strftime('%Y-%m-%d')
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT SUM(estimated_cost) FROM llm_costs WHERE substr(timestamp, 1, 10) = ?",
                    (date_str,)
                )
                result = cursor.fetchone()[0]
                return result if result is not None else 0.0
        except sqlite3.Error as e:
            logger.warning(f"Database error getting daily cost: {e}")
            return 0.0

    def get_monthly_cost(self, date: datetime) -> float:
        month_str = date.strftime('%Y-%m')
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT SUM(estimated_cost) FROM llm_costs WHERE substr(timestamp, 1, 7) = ?",
                    (month_str,)
                )
                result = cursor.fetchone()[0]
                return result if result is not None else 0.0
        except sqlite3.Error as e:
            logger.warning(f"Database error getting monthly cost: {e}")
            return 0.0

    def get_total_cost(self) -> float:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT SUM(estimated_cost) FROM llm_costs")
                result = cursor.fetchone()[0]
                return result if result is not None else 0.0
        except sqlite3.Error as e:
            logger.warning(f"Database error getting total cost: {e}")
            return 0.0

    def get_token_accuracy_report(self) -> dict:
        """Compare estimated vs actual tokens where actual data exists.

        Returns dict with per-model accuracy stats.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT model_name,
                           COUNT(*) as invocations,
                           SUM(prompt_tokens) as est_input,
                           SUM(completion_tokens) as est_output,
                           SUM(actual_input_tokens) as actual_input,
                           SUM(actual_output_tokens) as actual_output,
                           SUM(cached_tokens) as cached
                    FROM llm_costs
                    WHERE actual_input_tokens IS NOT NULL
                    GROUP BY model_name
                """)
                report = {}
                for row in cursor.fetchall():
                    model = row[0]
                    est_input = row[2] or 0
                    est_output = row[3] or 0
                    act_input = row[4] or 0
                    act_output = row[5] or 0
                    cached = row[6] or 0
                    report[model] = {
                        "invocations": row[1],
                        "estimated_input_tokens": est_input,
                        "estimated_output_tokens": est_output,
                        "actual_input_tokens": act_input,
                        "actual_output_tokens": act_output,
                        "cached_tokens": cached,
                        "input_accuracy": (act_input / est_input * 100) if est_input > 0 else 0,
                        "output_accuracy": (act_output / est_output * 100) if est_output > 0 else 0,
                    }
                return report
        except sqlite3.Error as e:
            logger.warning(f"Database error getting token accuracy: {e}")
            return {}

    def close(self):
        pass
