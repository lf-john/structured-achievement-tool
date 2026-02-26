from pydantic import BaseModel
import datetime

class BenchmarkResult(BaseModel):
    model_name: str
    prompt: str
    tokens_per_sec: float
    time_to_first_token: float
    total_response_time: float
    timestamp: datetime.datetime
