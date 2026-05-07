from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    script_path = Path(__file__).resolve().with_name("live_module_pass.py")
    command = [sys.executable, str(script_path), "--skip-factual-refresh", *sys.argv[1:]]
    completed = subprocess.run(command, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
