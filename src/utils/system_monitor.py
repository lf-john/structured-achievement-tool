"""
System Monitor Utility

Provides functions to collect memory and CPU usage metrics from the system.
"""

import re
import subprocess


def get_memory_usage():
    """
    Execute 'free -h' command and parse memory usage data.

    Returns:
        dict: Dictionary containing memory information with keys:
            - total: total memory (str)
            - used: used memory (str)
            - free: free memory (str)
            - available: available memory (str)
        Returns None if command fails or output is malformed.
    """
    try:
        # Execute free -h command
        result = subprocess.run(["free", "-h"], capture_output=True, text=True, check=True)

        output = result.stdout.strip()

        # Check for empty output
        if not output:
            return None

        # Parse memory line (Mem: line)
        # Expected format:
        # total        used        free      shared  buff/cache   available
        # 7.7Gi       4.2Gi       3.5Gi       1.1Gi       0.4Gi       5.2Gi
        # Mem:          7896       4200       3500       1100        400        5200
        lines = output.split("\n")

        for line in lines:
            if line.startswith("Mem:") or line.strip().startswith("Mem:"):
                parts = line.split()
                # Skip header, find Mem: line
                if len(parts) >= 7:
                    memory_info = {
                        "total": parts[1],
                        "used": parts[2],
                        "free": parts[3],
                        "shared": parts[4],
                        "buff/cache": parts[5],
                        "available": parts[6],
                    }
                    # Return only the keys expected by tests
                    return {
                        "total": memory_info["total"],
                        "used": memory_info["used"],
                        "free": memory_info["free"],
                        "available": memory_info["available"],
                    }
                break

        return None

    except subprocess.CalledProcessError:
        return None
    except Exception:
        return None


def get_cpu_load():
    """
    Execute uptime or /proc/loadavg and parse load averages.

    Returns:
        dict: Dictionary containing load averages with keys:
            - load: list of 3 load averages (1-min, 5-min, 15-min)
        Returns None if command fails or output is malformed.
    """
    try:
        # Try uptime first
        result = subprocess.run(["uptime"], capture_output=True, text=True, check=True)

        output = result.stdout.strip()

        # Parse load averages from uptime output
        # Expected format:
        # 12:34:56 up 45 days,  3:21,  2 users,  load average: 1.23, 1.45, 1.67
        match = re.search(r"load average:\s*([0-9.]+),\s*([0-9.]+),\s*([0-9.]+)", output)

        if match:
            load_averages = [float(match.group(1)), float(match.group(2)), float(match.group(3))]

            return {"load": load_averages}

        return None

    except subprocess.CalledProcessError:
        return None
    except Exception:
        return None
