#!/usr/bin/env python3
"""Launch BillReady React dashboard (prints instructions)."""

import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parent
    frontend = root / "frontend"

    print("BillReady React Dashboard")
    print("=" * 40)
    print("\n1. Start API (terminal 1):")
    print("   python run_api.py")
    print("\n2. Start frontend (terminal 2):")
    print("   cd frontend && npm install && npm run dev")
    print("\n3. Open http://localhost:5173")
    print()

    if not (frontend / "node_modules").exists():
        print("Installing frontend dependencies…")
        subprocess.check_call(["npm", "install"], cwd=frontend)

    return subprocess.call(["npm", "run", "dev"], cwd=frontend)


if __name__ == "__main__":
    sys.exit(main())
