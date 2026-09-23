import sys
from pathlib import Path

# Tests import `server` and `src.*` the way the container does (WORKDIR /app).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
