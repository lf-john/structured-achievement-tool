"""
Ollama Model Verifier

Query http://localhost:11434/api/tags to verify the availability of expected Ollama models:
- Qwen3 8B
- Qwen2.5-Coder 7B
- DeepSeek R1 8B
- Nemotron Mini
- nomic-embed-text
"""

import logging

import requests

# Configure logging
logger = logging.getLogger(__name__)


def get_expected_models() -> list[str]:
    """
    Get the list of expected model name substrings.

    Returns:
        List: List of expected model name substrings
    """
    return [
        "qwen",
        "qwen2.5-coder",
        "deepseek-r1",
        "nemotron-mini",
        "nomic-embed-text"
    ]


def _extract_model_core_parts(model_name: str) -> list[str]:
    """
    Extract core components from a model name for flexible matching.

    Args:
        model_name: The model name to extract components from

    Returns:
        List of core components for matching
    """
    # Remove common prefixes and suffixes
    parts = model_name.lower().strip()

    # Remove NVIDIA/ organization prefix
    if parts.startswith("nvidia/"):
        parts = parts.replace("nvidia/", "", 1)

    # Remove version suffixes (e.g., -v1, -v2, -1.5, -2, etc.)
    import re
    parts = re.sub(r'-v\d+(\.\d+)?$', '', parts)
    parts = re.sub(r'(?<!:)-\d+$', '', parts)  # Remove trailing numbers if not part of version (like :7b)
    parts = re.sub(r'(?<!:)-\d+b$', '', parts)  # Remove trailing 'b' if not part of version (like :7b)

    return parts.split('-')


def verify_ollama_models(api_url: str = "http://localhost:11434/api/tags") -> tuple[bool, list[str]]:
    """
    Verify that expected Ollama models are available.

    Args:
        api_url: URL of the Ollama API

    Returns:
        tuple: (bool indicating all models are available, list of available models)
    """
    try:
        # Query Ollama API for available models
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()

        # Parse the JSON response
        data = response.json()

        # Extract the models list
        models = data.get("models", [])

        # Handle missing or empty models list
        if not isinstance(models, list):
            logger.warning("Ollama API response did not contain a 'models' list")
            models = []

        # Get expected model names
        expected_models = get_expected_models()

        # Build list of available models
        available_models = []
        for model in models:
            if not isinstance(model, dict):
                continue
            model_name = model.get("name", "")
            if model_name:
                available_models.append(model_name)

        # Check if all expected models are present
        # We use flexible matching to handle model name variations
        found_models = []
        for expected in expected_models:
            # Normalize the expected model name
            expected_normalized = expected.lower()

            # Try to match available models to expected model
            for available in available_models:
                # Normalize the available model name
                available_normalized = available.lower()

                # Try direct substring match (case-insensitive)
                if expected_normalized in available_normalized:
                    found_models.append(expected)
                    break

            if expected in found_models:
                break

        # All expected models are available if we found all of them
        all_available = len(found_models) == len(expected_models)

        logger.info(f"Available models: {available_models}")
        logger.info(f"Expected models: {expected_models}")
        logger.info(f"Found models: {found_models}")
        logger.info(f"All available: {all_available}")

        return all_available, available_models

    except requests.ConnectionError:
        logger.error("Failed to connect to Ollama API. Is Ollama running?")
        return False, []
    except requests.Timeout:
        logger.error("Connection to Ollama API timed out")
        return False, []
    except requests.HTTPError as e:
        logger.error(f"Ollama API returned HTTP error: {e}")
        return False, []
    except ValueError as e:
        logger.error(f"Failed to parse Ollama API response as JSON: {e}")
        return False, []
    except Exception as e:
        logger.error(f"Unexpected error verifying Ollama models: {e}")
        return False, []
