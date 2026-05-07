from __future__ import annotations

import argparse
import sys
from pathlib import Path


# Allow loose script execution from a source checkout without requiring pip install -e .
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _REPO_ROOT / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from project_introspector.run_validator import validate_run_directory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a project-introspector run directory.")
    parser.add_argument("run_dir")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = validate_run_directory(Path(args.run_dir))
    if report.ok:
        print("OK: run_result.json matches run contract")
    else:
        print("FAILED: run_result.json does not match run contract")
    for finding in report.findings:
        print(f"{finding.severity.value.upper()}: {finding.code}: {finding.message}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
