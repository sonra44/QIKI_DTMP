from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import quote

import httpx


def _write_json(path: Path, payload: object, *, pretty: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None, sort_keys=pretty) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export analyzer project report to a local JSON file.")
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--analyzer-url", default="http://127.0.0.1:8015")
    parser.add_argument("--out", required=True)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--no-pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_url = args.analyzer_url.rstrip("/")
    out = Path(args.out)
    report_url = f"{base_url}/report/{quote(args.project_name, safe='')}"
    try:
        with httpx.Client(timeout=args.timeout) as client:
            response = client.get(report_url)
            response.raise_for_status()
            data = response.json()
    except httpx.ConnectError:
        print(f"ERROR: could not connect to analyzer at {base_url}", file=sys.stderr)
        print("Hint: start analyzer or use the correct --analyzer-url.", file=sys.stderr)
        return 2
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code if exc.response is not None else 0
        if status_code == 404:
            print(f"ERROR: report for project {args.project_name} was not found.", file=sys.stderr)
            print("Hint: run scan_project.py first or check --project-name.", file=sys.stderr)
            return 3
        print(f"ERROR: analyzer returned HTTP {status_code} while exporting report.", file=sys.stderr)
        return 4
    except ValueError:
        print("ERROR: analyzer returned non-JSON response.", file=sys.stderr)
        return 5
    except httpx.HTTPError as exc:
        print(f"ERROR: could not export report: {exc}", file=sys.stderr)
        return 2
    if not isinstance(data, dict):
        print("ERROR: analyzer returned non-object JSON response.", file=sys.stderr)
        return 5
    try:
        _write_json(out, data, pretty=not args.no_pretty)
    except OSError as exc:
        print(f"ERROR: could not write report to {out}: {exc}", file=sys.stderr)
        return 6
    print(f"Exported report for {args.project_name}")
    print(f"Analyzer: {base_url}")
    print(f"Output: {out}")
    print(f"Report version: {data.get('report_version', 'unknown')}")
    print(f"Status: {data.get('status', data.get('factual_layer', {}).get('status', 'unknown'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
