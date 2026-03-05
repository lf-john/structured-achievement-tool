import re


class ResponseParser:
    def parse_ollama_response(self, response: str) -> tuple[int, float]:
        match = re.search(r"Score: (\d+), Confidence: ([0-9.]+)", response)
        if match:
            score = int(match.group(1))
            confidence = float(match.group(2))
            if not (1 <= score <= 100):
                raise ValueError("Extracted score is not within the valid range (1-100)")
            if not (0.0 <= confidence <= 1.0):
                raise ValueError("Extracted confidence is not within the valid range (0.0-1.0)")
            return score, confidence
        else:
            raise ValueError("Invalid response format: Could not extract score and confidence")
