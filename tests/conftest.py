"""
pytest configuration for the project.
This file ensures that the src directory is in the Python path.
"""

import sys
from pathlib import Path

# Add the project root directory to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
