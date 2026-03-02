import csv
import os
from datetime import datetime


class ValidationLogger:
    COLUMNS = ("email", "classification", "data_quality", "score", "timestamp")

    def __init__(self, output_path: str):
        self.output_path = output_path

    def log_result(
        self,
        email: str,
        classification: str,
        data_quality: str,
        score: float,
    ) -> None:
        file_exists = os.path.exists(self.output_path)
        with open(self.output_path, "a", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=self.COLUMNS)
            if not file_exists:
                writer.writeheader()
            writer.writerow(
                {
                    "email": email,
                    "classification": classification,
                    "data_quality": data_quality,
                    "score": score,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
