"""Generate final-results PNGs (guild standings, leaderboard, score race)
once the competition is over.

Usage:
    DATABASE_URL=... uv run python scripts/generate_final_reports.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from reports.final import generate_all


def main() -> None:
    paths = generate_all()
    if not paths:
        print("[report] nothing generated")
        return
    print("[report] generated:")
    for p in paths:
        print(f"  {p}")


if __name__ == "__main__":
    main()
