import re
import logging
from typing import Dict, Any
from default_api import run_shell_command

logger = logging.getLogger(__name__)

class OllamaGPUMonitor:
    def __init__(self):
        pass

    def get_gpu_utilization(self) -> float:
        """
        Retrieves the current GPU utilization for Ollama.
        Executes 'nvidia-smi' and parses the output.
        Returns utilization as a float between 0.0 and 1.0, or 0.0 if an error occurs.
        """
        command = "nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits"
        description = "Get Ollama GPU utilization"
        try:
            result = run_shell_command(command=command, description=description)
            output = result.get("output", "").strip()
            if output and output.isdigit():
                utilization_percent = float(output)
                return utilization_percent / 100.0
            else:
                logger.warning(f"Could not parse GPU utilization from nvidia-smi output: {output}")
                return 0.0
        except Exception as e:
            logger.error(f"Error getting GPU utilization with nvidia-smi: {e}")
            return 0.0
