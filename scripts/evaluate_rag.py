#!/usr/bin/env python
"""Backward-compatible entry point for System 6 evaluation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluations.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
