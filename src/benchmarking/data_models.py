import datetime

from pydantic import BaseModel


class BenchmarkResult(BaseModel):
    model_name: str
    prompt: str
    tokens_per_sec: float
    time_to_first_token: float
    total_response_time: float
    timestamp: datetime.datetime
