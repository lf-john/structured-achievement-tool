import json
from dataclasses import dataclass
from datetime import datetime

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
                obj = {
                    'timestamp': log.timestamp.isoformat(),
                    'event': log.event,
                    'level': log.level,
                    'details': log.details,
                }
                f.write(json.dumps(obj) + '\n')

    def load(self, filepath: str):
        with open(filepath, 'r') as f:
            lines = f.readlines()
        self._logs = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            self._logs.append(NotificationLog(
                timestamp=datetime.fromisoformat(obj['timestamp']),
                event=obj['event'],
                level=obj['level'],
                details=obj['details'],
            ))
