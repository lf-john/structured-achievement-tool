import re
import logging
import subprocess

logger = logging.getLogger(__name__)

class OllamaGPUMonitor:
    def __init__(self):
        pass

    def get_gpu_utilization(self) -> float:
        try:
            # Use subprocess to run the shell command
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                check=True # Raise an exception for non-zero exit codes
            )
            
            utilization_str = result.stdout.strip()
            if not utilization_str:
                logger.warning("nvidia-smi returned empty output.")
                return 0.0

            # The output is a percentage, e.g., "75". Convert to float 0.0-1.0
            utilization = float(utilization_str) / 100.0
            return utilization
        except FileNotFoundError:
            logger.error("'nvidia-smi' command not found. Is NVIDIA driver installed?")
            return 0.0
        except subprocess.CalledProcessError as e:
            logger.error(f"nvidia-smi command failed with error: {e}\nStderr: {e.stderr}")
            return 0.0
        except ValueError as e:
            logger.error(f"Error parsing GPU utilization output '{utilization_str}': {e}")
            return 0.0
        except Exception as e:
            logger.error(f"Unexpected error in get_gpu_utilization: {e}")
            return 0.0
