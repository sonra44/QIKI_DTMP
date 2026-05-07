from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


# Allow loose script execution from a source checkout without requiring pip install -e .
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _REPO_ROOT / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from project_introspector.run_contract import (
    ArtifactKind,
    IssueSeverity,
    LayerStatus,
    RunArtifactRef,
    RunEnrichmentLayer,
    RunFactualLayer,
    RunIssue,
    RunMode,
    RunNextStep,
    RunReportLayer,
    RunResult,
    RunRuntimeLayer,
    RunStatus,
)
from project_introspector.run_validator import normalize_run_result, validate_run_result


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_run_id(project_name: str) -> str:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    safe = ''.join(ch if ch.isalnum() or ch in {'-', '_'} else '_' for ch in project_name)
    return f'{stamp}_{safe}'


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    tmp.replace(path)


def _model_dump(model: Any) -> dict[str, Any]:
    if hasattr(model, 'model_dump'):
        return model.model_dump(mode='json')
    return json.loads(model.json())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run a complete local project-introspector analysis package.')
    parser.add_argument('--project-name', required=True)
    parser.add_argument('--source-root', required=True)
    parser.add_argument('--out-dir', required=True)
    parser.add_argument('--analyzer-url', default='http://127.0.0.1:8015')
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--enrich', action='store_true')
    parser.add_argument('--module', action='append', default=[])
    parser.add_argument('--max-modules', type=int, default=None)
    parser.add_argument('--allow-unconfigured-provider', action='store_true')
    parser.add_argument('--run-id', default=None)
    parser.add_argument('--keep-going', action='store_true')
    parser.add_argument('--timeout', type=float, default=30.0)
    return parser.parse_args()


class ProgressLog:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, message: str) -> None:
        self.path.write_text('', encoding='utf-8') if not self.path.exists() else None
        with self.path.open('a', encoding='utf-8') as handle:
            handle.write(f'{_utc_now()} {message}\n')
        print(message)


def _run_subprocess(command: list[str], *, log: ProgressLog) -> int:
    log.write('exec ' + ' '.join(command))
    completed = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if completed.stdout:
        with log.path.open('a', encoding='utf-8') as handle:
            handle.write(completed.stdout)
            if not completed.stdout.endswith('\n'):
                handle.write('\n')
    return completed.returncode


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _fetch_json(url: str, *, timeout: float) -> dict[str, Any]:
    with httpx.Client(timeout=timeout) as client:
        response = client.get(url)
        response.raise_for_status()
        payload = response.json()
    return payload if isinstance(payload, dict) else {}


def _build_result(
    *,
    args: argparse.Namespace,
    run_id: str,
    run_dir: Path,
    started_at: str,
    completed_at: str,
    scan_summary: dict[str, Any],
    llm_status: dict[str, Any],
    report: dict[str, Any],
    mode: RunMode,
) -> RunResult:
    modules_scanned = int(scan_summary.get('modules_scanned') or 0)
    scan_errors = int(scan_summary.get('scan_errors') or 0)
    runtime_count = int(
        scan_summary.get('factual_layer', {}).get('runtime_event_count')
        if isinstance(scan_summary.get('factual_layer'), dict)
        else 0
    )
    if report:
        runtime_count = int(report.get('runtime_layer', {}).get('runtime_event_count') or runtime_count)
    provider_configured = bool(llm_status.get('configured'))
    report_ready = bool(report)
    offline = mode == RunMode.OFFLINE
    limits: list[RunIssue] = []
    next_steps: list[RunNextStep] = []
    if runtime_count == 0:
        limits.append(RunIssue(code='runtime_absent', severity=IssueSeverity.INFO, message='No runtime events were available for this run.', layer='runtime'))
    if offline:
        limits.append(RunIssue(code='offline_mode', severity=IssueSeverity.INFO, message='Run completed without analyzer-backed report or enrichment.'))
        next_steps.append(RunNextStep(code='start_analyzer', message='Start analyzer and run analyzer-backed mode when report/enrichment are needed.', priority=20))
    elif not provider_configured:
        limits.append(RunIssue(code='llm_provider_unconfigured', severity=IssueSeverity.INFO, message='LLM provider was not configured; enrichment was skipped.', layer='enrichment'))
        next_steps.append(RunNextStep(code='configure_provider', message='Configure an LLM provider to enable enrichment.', priority=30))
    next_steps.append(RunNextStep(code='review_report', message='Review generated artifacts and limitations before acting on derived findings.', priority=10))

    artifacts = [
        RunArtifactRef(kind=ArtifactKind.STATIC_SNAPSHOT, path='static_snapshot.json', required=True),
        RunArtifactRef(kind=ArtifactKind.SCAN_SUMMARY, path='summary.json', required=True),
        RunArtifactRef(kind=ArtifactKind.SCHEMA, path='schema.json', required=True),
        RunArtifactRef(kind=ArtifactKind.PROGRESS_LOG, path='logs/progress.log', required=True),
    ]
    if report_ready:
        artifacts.append(RunArtifactRef(kind=ArtifactKind.REPORT, path='report.json', required=not offline))
    if llm_status:
        artifacts.append(RunArtifactRef(kind=ArtifactKind.LLM_STATUS, path='llm_status.json', required=False))

    status = RunStatus.COMPLETED_WITH_LIMITS if limits else RunStatus.COMPLETED
    if scan_errors:
        status = RunStatus.DEGRADED
        limits.append(RunIssue(code='scan_errors_present', severity=IssueSeverity.WARNING, message='Static scan completed with scan errors.', layer='factual'))

    return RunResult(
        run_id=run_id,
        project_name=args.project_name,
        source_root=str(Path(args.source_root).resolve()),
        mode=mode,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
        factual_layer=RunFactualLayer(
            status=LayerStatus.READY if scan_errors == 0 else LayerStatus.DEGRADED,
            modules_scanned=modules_scanned,
            scan_errors=scan_errors,
            snapshot_path='static_snapshot.json',
            schema_path='schema.json',
        ),
        runtime_layer=RunRuntimeLayer(
            status=LayerStatus.ABSENT if runtime_count == 0 else LayerStatus.READY,
            runtime_event_count=runtime_count,
        ),
        enrichment_layer=RunEnrichmentLayer(
            status=LayerStatus.SKIPPED if not args.enrich else (LayerStatus.READY if provider_configured else LayerStatus.SKIPPED),
            provider_configured=provider_configured,
            llm_status_path='llm_status.json' if llm_status else None,
            module_findings_dir='module_findings' if (run_dir / 'module_findings').exists() else None,
        ),
        report_layer=RunReportLayer(
            status=LayerStatus.READY if report_ready else (LayerStatus.SKIPPED if offline else LayerStatus.FAILED),
            report_path='report.json' if report_ready else None,
            report_version=str(report.get('report_version')) if report.get('report_version') else None,
        ),
        artifacts=artifacts,
        limits=limits,
        next_safe_steps=next_steps,
    )


def main() -> int:
    args = parse_args()
    started_at = _utc_now()
    run_id = args.run_id or _default_run_id(args.project_name)
    run_dir = Path(args.out_dir).resolve() / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / 'logs').mkdir(parents=True, exist_ok=True)
    log = ProgressLog(run_dir / 'logs' / 'progress.log')
    log.write(f'start run_id={run_id}')

    mode = RunMode.OFFLINE if args.offline else RunMode.FULL if args.enrich else RunMode.ANALYZER_BACKED
    scan_cmd = [
        sys.executable,
        str(Path(__file__).resolve().parent / 'scan_project.py'),
        '--project-name', args.project_name,
        '--source-root', args.source_root,
        '--output-dir', str(run_dir),
        '--snapshot-out', str(run_dir / 'static_snapshot.json'),
        '--summary-out', str(run_dir / 'summary.json'),
        '--schema-out', str(run_dir / 'schema.json'),
    ]
    if args.offline:
        scan_cmd.append('--offline')
    else:
        scan_cmd.extend(['--analyzer-url', args.analyzer_url])
    code = _run_subprocess(scan_cmd, log=log)
    if code != 0 and not args.keep_going:
        log.write(f'factual_scan failed exit_code={code}')
        failed = RunResult(
            run_id=run_id,
            project_name=args.project_name,
            source_root=str(Path(args.source_root).resolve()),
            mode=mode,
            status=RunStatus.FAILED,
            started_at=started_at,
            completed_at=_utc_now(),
            factual_layer=RunFactualLayer(status=LayerStatus.FAILED),
            report_layer=RunReportLayer(status=LayerStatus.FAILED),
            artifacts=[RunArtifactRef(kind=ArtifactKind.PROGRESS_LOG, path='logs/progress.log', required=True)],
            limits=[RunIssue(code='factual_scan_failed', severity=IssueSeverity.ERROR, message='scan_project.py failed.', layer='factual')],
        )
        _write_json(run_dir / 'run_result.json', _model_dump(failed))
        return code or 1

    llm_status: dict[str, Any] = {}
    report: dict[str, Any] = {}
    if not args.offline:
        try:
            llm_status = _fetch_json(f"{args.analyzer_url.rstrip('/')}/llm/status", timeout=args.timeout)
            _write_json(run_dir / 'llm_status.json', llm_status)
            log.write(f"llm_status fetched configured={bool(llm_status.get('configured'))}")
        except Exception as exc:
            log.write(f'llm_status fetch failed {type(exc).__name__}: {exc}')

        if args.enrich and (llm_status.get('configured') or args.allow_unconfigured_provider):
            module_findings = run_dir / 'module_findings'
            enrich_cmd = [
                sys.executable,
                str(Path(__file__).resolve().parent / 'live_module_pass.py'),
                '--project-name', args.project_name,
                '--source-root', args.source_root,
                '--output-dir', str(module_findings),
                '--analyzer-url', args.analyzer_url,
                '--skip-factual-refresh',
            ]
            for module in args.module:
                enrich_cmd.extend(['--module', module])
            if args.allow_unconfigured_provider:
                enrich_cmd.append('--allow-unconfigured-provider')
            code = _run_subprocess(enrich_cmd, log=log)
            if code != 0:
                log.write(f'enrichment failed exit_code={code}')

        export_cmd = [
            sys.executable,
            str(Path(__file__).resolve().parent / 'export_report.py'),
            '--project-name', args.project_name,
            '--analyzer-url', args.analyzer_url,
            '--out', str(run_dir / 'report.json'),
        ]
        code = _run_subprocess(export_cmd, log=log)
        if code == 0:
            report = _load_json(run_dir / 'report.json')
        else:
            log.write(f'report export failed exit_code={code}')

    scan_summary = _load_json(run_dir / 'summary.json')
    result = _build_result(
        args=args,
        run_id=run_id,
        run_dir=run_dir,
        started_at=started_at,
        completed_at=_utc_now(),
        scan_summary=scan_summary,
        llm_status=llm_status,
        report=report,
        mode=mode,
    )
    validation = validate_run_result(run_dir, result)
    result = normalize_run_result(run_dir, result, validation)
    _write_json(run_dir / 'run_result.json', _model_dump(result))
    log.write(f'run_result written status={result.status.value}')
    print(f'Run directory: {run_dir}')
    return 0 if result.status != RunStatus.FAILED else 1


if __name__ == '__main__':
    raise SystemExit(main())
