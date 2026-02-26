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
                CREATE TABLE IF NOT EXISTS llm_cost_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    prompt_tokens INTEGER NOT NULL,
                    completion_tokens INTEGER NOT NULL,
                    cost REAL NOT NULL
                )
            """)
            conn.commit()

    def add_log_entry(self, model_name: str, prompt_tokens: int, completion_tokens: int, cost: float):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                timestamp = datetime.now().isoformat()
                cursor.execute(
                    "INSERT INTO llm_cost_logs (timestamp, model_name, prompt_tokens, completion_tokens, cost) VALUES (?, ?, ?, ?, ?)",
                    (timestamp, model_name, prompt_tokens, completion_tokens, cost)
                )
                conn.commit()
        except sqlite3.Error as e:
            # In a real application, this would use a proper logging mechanism
            print(f"Database error adding log entry: {e}")

    def get_daily_cost(self) -> float:
        today = datetime.now().strftime('%Y-%m-%d')
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT SUM(cost) FROM llm_cost_logs WHERE substr(timestamp, 1, 10) = ?",
                    (today,)
                )
                result = cursor.fetchone()[0]
                return result if result is not None else 0.0
        except sqlite3.Error as e:
            print(f"Database error getting daily cost: {e}")
            return 0.0

    def get_monthly_cost(self) -> float:
        current_month = datetime.now().strftime('%Y-%m')
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT SUM(cost) FROM llm_cost_logs WHERE substr(timestamp, 1, 7) = ?",
                    (current_month,)
                )
                result = cursor.fetchone()[0]
                return result if result is not None else 0.0
        except sqlite3.Error as e:
            print(f"Database error getting monthly cost: {e}")
            return 0.0

    def close(self):
        # In a typical application, connections are managed by 'with' statements,
        # but a close method might be useful for explicit cleanup if connections are held longer.
        pass
