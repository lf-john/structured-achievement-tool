"""Ollama Benchmark Infrastructure module."""

from .config import MODELS, PROMPTS, OLLAMA_API_BASE_URL
from .data_models import BenchmarkResult
from .ollama_client import OllamaClient

__all__ = [
    'MODELS',
    'PROMPTS',
    'OLLAMA_API_BASE_URL',
    'BenchmarkResult',
    'OllamaClient',
]
