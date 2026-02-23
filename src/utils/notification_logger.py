from dataclasses import dataclass
from datetime import datetime
import json


VALID_LEVELS = {'info', 'warn', 'error'}


@dataclass
class NotificationLog:
    timestamp: datetime
    event: str
    level: str
    details: str

    def __post_init__(self):
        if self.level not in VALID_LEVELS:
            raise ValueError(f"level must be one of {VALID_LEVELS}, got {self.level!r}")


class NotificationLogger:
    def __init__(self):
        self._logs = []

    def log(self, event: str, level: str, details: str):
        entry = NotificationLog(
            timestamp=datetime.utcnow(),
            event=event,
            level=level,
            details=details,
        )
        self._logs.append(entry)

    def get_logs(self, level=None):
        if level is None:
            return list(self._logs)
        return [log for log in self._logs if log.level == level]

    def save(self, filepath: str):
        with open(filepath, 'w') as f:
            for log in self._logs:
                record = {
                    'timestamp': log.timestamp.isoformat(),
                    'event': log.event,
                    'level': log.level,
                    'details': log.details,
                }
                f.write(json.dumps(record) + '\n')

    def load(self, filepath: str):
        logs = []
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                log = NotificationLog(
                    timestamp=datetime.fromisoformat(data['timestamp']),
                    event=data['event'],
                    level=data['level'],
                    details=data['details'],
                )
                logs.append(log)
        self._logs = logs
