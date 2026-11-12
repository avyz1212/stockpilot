#!/usr/bin/env python3
"""Zero-install entry point: `python3 run.py demo` (no pip, no dependencies)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from stockpilot.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
