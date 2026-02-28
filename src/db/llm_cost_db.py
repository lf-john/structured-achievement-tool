import sqlite3
import os
from datetime import datetime

class LLMCostDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._initialize_db()

    def _initialize_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
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
            conn.commit()

    def add_log_entry(self, model_name: str, prompt_tokens: int, completion_tokens: int, estimated_cost: float, timestamp: datetime = None):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                ts = (timestamp or datetime.now()).isoformat()
                cursor.execute(
                    "INSERT INTO llm_costs (timestamp, model_name, prompt_tokens, completion_tokens, estimated_cost) VALUES (?, ?, ?, ?, ?)",
                    (ts, model_name, prompt_tokens, completion_tokens, estimated_cost)
                )
                conn.commit()
        except sqlite3.Error as e:
            # In a real application, this would use a proper logging mechanism
            print(f"Database error adding log entry: {e}")

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
            print(f"Database error getting daily cost: {e}")
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
            print(f"Database error getting monthly cost: {e}")
            return 0.0

    def get_total_cost(self) -> float:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT SUM(estimated_cost) FROM llm_costs")
                result = cursor.fetchone()[0]
                return result if result is not None else 0.0
        except sqlite3.Error as e:
            print(f"Database error getting total cost: {e}")
            return 0.0

    def close(self):
        # In a typical application, connections are managed by 'with' statements,
        # but a close method might be useful for explicit cleanup if connections are held longer.
        pass
