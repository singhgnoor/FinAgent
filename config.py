"""
Project-wide path configuration.
Resolves the project directories.
"""

from pathlib import Path

# DEBUG -
VERBOSE = True


## Dirs
BASE_DIR = Path(__file__).resolve().parent


## Agent Specific configuration

DEFAULT_ALERT_THRESHOLD = 70  # Decision Agent

# RAG Agent
TOP_K_DEFAULT = 3

if __name__ == '__main__':
    print(f"Project root : {BASE_DIR}")