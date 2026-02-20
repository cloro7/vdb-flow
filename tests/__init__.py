"""Tests package."""

from pathlib import Path
import sys

# Ensure the src/ directory (which contains the vdb_flow package) is importable
_SRC_PATH = Path(__file__).resolve().parents[1] / "src"
if str(_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(_SRC_PATH))
