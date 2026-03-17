"""pytest configuration – ensures project root is on sys.path.

This means `pytest tests/` works even without a prior `pip install -e .`,
which is useful in CI environments or fresh checkouts.
"""
import sys
from pathlib import Path

# Insert project root so `tarapath_core` is importable.
sys.path.insert(0, str(Path(__file__).parent.parent))
