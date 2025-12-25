
from __future__ import annotations

import runpy
from pathlib import Path


def main() -> int:
    # Delegate to the repo-root generator (single source of truth).
    root_gen = Path(__file__).resolve().parents[1] / "generate_project.py"
    if not root_gen.exists():
        raise SystemExit("Root generate_project.py not found. Run from repo root.")
    runpy.run_path(str(root_gen), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
