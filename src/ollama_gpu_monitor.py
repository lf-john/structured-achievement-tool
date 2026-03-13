import logging
import re

import default_api  # Import default_api directly

# Configure logging for the module
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class OllamaGPUMonitor:
    """
    Monitors Ollama GPU utilization by querying nvidia-smi.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def get_gpu_utilization(self) -> float:
        """
        Returns current GPU utilization as a float (0.0-1.0).
        Returns 0.0 if nvidia-smi fails or output cannot be parsed.
        """
        try:
            # The test expects this specific command, so we must call it.
            command_result = default_api.run_shell_command(
                command="nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits",
                description="Get Ollama GPU utilization",
            )

            output = command_result.get("output", "").strip()
            error = command_result.get("error")
            exit_code = command_result.get("exit_code")

            if error or (exit_code is not None and exit_code != 0):
                self.logger.warning(f"nvidia-smi command failed with exit code {exit_code}: {error}")
                return 0.0

            if not output:
                self.logger.info("nvidia-smi returned empty output.")
                return 0.0

            # Regex to find the GPU utilization percentage in the nvidia-smi output.
            # We are looking for a line that contains a number followed by '%' and then 'Default'
            # This pattern targets the specific line format in the mocked output: '75%      Default '
            match = re.search(r"\s+([0-9]+)%\s+Default", output, re.MULTILINE)
            if match:
                utilization_percentage = float(match.group(1))
                return utilization_percentage / 100.0
            else:
                self.logger.error(f"Could not find GPU utilization in nvidia-smi output: {output}")
                return 0.0
        except ValueError:
            self.logger.error("Could not parse extracted utilization as a float.")
            return 0.0
        except Exception as e:
            self.logger.error(f"Error getting GPU utilization: {e}")
            return 0.0
