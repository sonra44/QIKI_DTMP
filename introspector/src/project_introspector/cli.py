from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


def _repo_root() -> Path:
    # Source-tree first; this CLI is intentionally transitional until loose scripts are internalized.
    return Path(__file__).resolve().parents[2]


def _run_script(script_name: str, args: list[str]) -> int:
    script = _repo_root() / 'scripts' / script_name
    if not script.exists():
        print(f'ERROR: script not found: {script}', file=sys.stderr)
        return 2
    completed = subprocess.run([sys.executable, str(script), *args])
    return int(completed.returncode)


@dataclass(frozen=True)
class TuiHealthResult:
    status: str
    textual_available: bool
    analyzer_checked: bool
    analyzer_url: str
    project_name: str | None
    analyzer_status: dict[str, object] | None = None
    error: str | None = None


def _textual_available() -> bool:
    return importlib.util.find_spec('textual') is not None


def _fetch_analyzer_status(analyzer_url: str, timeout: float) -> dict[str, object]:
    url = analyzer_url.rstrip('/') + '/llm/status'
    with urlopen(url, timeout=timeout) as response:
        payload = response.read().decode('utf-8')
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError('analyzer /llm/status did not return a JSON object')
    return data


def run_tui_health(
    *,
    analyzer_url: str,
    project_name: str | None,
    check_analyzer: bool,
    timeout: float,
) -> int:
    if not _textual_available():
        result = TuiHealthResult(
            status='missing_tui_dependency',
            textual_available=False,
            analyzer_checked=False,
            analyzer_url=analyzer_url,
            project_name=project_name,
            error='Textual is not installed',
        )
        print(json.dumps(asdict(result), sort_keys=True))
        return 2

    if not check_analyzer:
        result = TuiHealthResult(
            status='ok',
            textual_available=True,
            analyzer_checked=False,
            analyzer_url=analyzer_url,
            project_name=project_name,
        )
        print(json.dumps(asdict(result), sort_keys=True))
        return 0

    try:
        analyzer_status = _fetch_analyzer_status(analyzer_url, timeout=timeout)
    except (OSError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        result = TuiHealthResult(
            status='analyzer_unavailable',
            textual_available=True,
            analyzer_checked=True,
            analyzer_url=analyzer_url,
            project_name=project_name,
            error=f'{type(exc).__name__}: {exc}',
        )
        print(json.dumps(asdict(result), sort_keys=True))
        return 3

    result = TuiHealthResult(
        status='ok',
        textual_available=True,
        analyzer_checked=True,
        analyzer_url=analyzer_url,
        project_name=project_name,
        analyzer_status=analyzer_status,
    )
    print(json.dumps(asdict(result), sort_keys=True))
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog='project-introspector', description='Operator CLI for project-introspector.')
    sub = parser.add_subparsers(dest='command', required=True)

    scan = sub.add_parser('scan', help='Run factual scan and optionally upload it to analyzer.')
    scan.add_argument('--project-name', default='INTROSPECTOR_DEMO')
    scan.add_argument('--source-root', default=str(_repo_root() / 'src'))
    scan.add_argument('--output-dir', default=str(_repo_root() / 'tmp' / 'project_scan'))
    scan.add_argument('--analyzer-url', default='http://127.0.0.1:8015')
    scan.add_argument('--offline', action='store_true')
    scan.add_argument('--no-upload', action='store_true')

    report = sub.add_parser('report', help='Export analyzer report to a local JSON file.')
    report.add_argument('--project-name', required=True)
    report.add_argument('--analyzer-url', default='http://127.0.0.1:8015')
    report.add_argument('--out', required=True)

    run = sub.add_parser('run', help='Create a completed run directory and run_result.json.')
    run.add_argument('--project-name', required=True)
    run.add_argument('--source-root', required=True)
    run.add_argument('--out-dir', required=True)
    run.add_argument('--analyzer-url', default='http://127.0.0.1:8015')
    run.add_argument('--offline', action='store_true')
    run.add_argument('--enrich', action='store_true')
    run.add_argument('--allow-unconfigured-provider', action='store_true')
    run.add_argument('--module', action='append', default=[])
    run.add_argument('--max-modules', type=int, default=None)
    run.add_argument('--run-id', default=None)
    run.add_argument('--keep-going', action='store_true')
    run.add_argument('--timeout', type=float, default=30.0)

    validate = sub.add_parser('validate', help='Validate a completed run directory.')
    validate.add_argument('run_dir')

    tui = sub.add_parser('tui', help='Start Textual TUI.')
    tui.add_argument('--analyzer-url', default=None)
    tui.add_argument('--project-name', default=None)

    tui_health = sub.add_parser('tui-health', help='Check TUI readiness without starting Textual UI.')
    tui_health.add_argument('--analyzer-url', default='http://127.0.0.1:8015')
    tui_health.add_argument('--project-name', default=None)
    tui_health.add_argument('--check-analyzer', action='store_true')
    tui_health.add_argument('--timeout', type=float, default=2.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == 'scan':
        cmd = [
            '--project-name', args.project_name,
            '--source-root', args.source_root,
            '--output-dir', args.output_dir,
            '--analyzer-url', args.analyzer_url,
        ]
        if args.offline:
            cmd.append('--offline')
        if args.no_upload:
            cmd.append('--no-upload')
        return _run_script('scan_project.py', cmd)
    if args.command == 'report':
        return _run_script('export_report.py', ['--project-name', args.project_name, '--analyzer-url', args.analyzer_url, '--out', args.out])
    if args.command == 'run':
        cmd = ['--project-name', args.project_name, '--source-root', args.source_root, '--out-dir', args.out_dir, '--analyzer-url', args.analyzer_url]
        for module_name in args.module:
            cmd.extend(['--module', module_name])
        if args.max_modules is not None:
            cmd.extend(['--max-modules', str(args.max_modules)])
        if args.run_id:
            cmd.extend(['--run-id', args.run_id])
        if args.keep_going:
            cmd.append('--keep-going')
        cmd.extend(['--timeout', str(args.timeout)])
        if args.offline:
            cmd.append('--offline')
        if args.enrich:
            cmd.append('--enrich')
        if args.allow_unconfigured_provider:
            cmd.append('--allow-unconfigured-provider')
        return _run_script('run_full_local_analysis.py', cmd)
    if args.command == 'validate':
        return _run_script('validate_run_result.py', [args.run_dir])
    if args.command == 'tui':
        from .tui_app import main as tui_main

        return int(tui_main() or 0)
    if args.command == 'tui-health':
        return run_tui_health(
            analyzer_url=args.analyzer_url,
            project_name=args.project_name,
            check_analyzer=args.check_analyzer,
            timeout=args.timeout,
        )
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
