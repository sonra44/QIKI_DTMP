from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query

from analyzer.storage import AnalyzerStorage
from project_introspector.llm import ModuleEnrichmentProvider, build_enrichment_client_from_env, get_provider_settings_from_env
from project_introspector.models import LLMModuleAnalysis, LLMProjectAnalysis, RuntimeEvent, StaticScanEnvelope
from project_introspector.report_quality import compose_project_report
from project_introspector.schema_builder import build_schema

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent / 'data'
DATA_DIR.mkdir(parents=True, exist_ok=True)
ANALYZER_BUILD_MARKER = 'repo-freshness-2026-04-04-api-live-artifacts-emitter-health'

app = FastAPI(title='project-introspector-analyzer')
_STORAGE_CACHE: AnalyzerStorage | None = None
_STORAGE_CACHE_KEY: str | None = None


def _get_storage() -> AnalyzerStorage:
    global _STORAGE_CACHE, _STORAGE_CACHE_KEY
    current_key = str(DATA_DIR.resolve())
    if _STORAGE_CACHE is None or _STORAGE_CACHE_KEY != current_key:
        _STORAGE_CACHE = AnalyzerStorage(DATA_DIR)
        _STORAGE_CACHE_KEY = current_key
    return _STORAGE_CACHE


def _load_schema(project_name: str):
    storage = _get_storage()
    snapshot = storage.load_static(project_name)
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f'Missing static snapshot for {project_name}')

    warnings: list[str] = []
    runtime_events = storage.load_runtime(project_name, warnings=warnings)
    schema = build_schema(snapshot, runtime_events)
    if warnings:
        schema.notes = list(dict.fromkeys([*schema.notes, *warnings]))
    return schema


def _provider_not_configured_detail(settings) -> str:
    provider = settings.provider_name or 'provider'
    return f'{provider} credentials are not configured'


@app.post('/events/static')
def ingest_static(payload: StaticScanEnvelope):
    _get_storage().write_static(payload)
    return {
        'status': 'ok',
        'modules': len(payload.modules),
        'scan_errors': len(payload.scan_errors),
    }


@app.post('/events/runtime')
def ingest_runtime(payload: list[RuntimeEvent]):
    if not payload:
        return {'status': 'ok', 'events': 0}
    project_names = {event.project_name for event in payload}
    if len(project_names) != 1:
        raise HTTPException(status_code=400, detail='All runtime events in one batch must share project_name')
    _get_storage().append_runtime(payload)
    return {'status': 'ok', 'events': len(payload)}


@app.get('/schema/{project_name}')
def get_schema(project_name: str):
    return _load_schema(project_name).model_dump(mode='json')


@app.get('/llm/status')
def llm_status():
    settings = get_provider_settings_from_env()
    storage = _get_storage()
    health = storage.health()
    return {
        'configured': settings.configured,
        'provider_credentials_configured': settings.configured,
        'provider_probe_status': 'not_checked',
        'base_url': settings.base_url,
        'default_model': settings.default_model,
        'fallback_model': settings.fallback_model,
        'app_name': settings.app_name,
        'provider_name': settings.provider_name,
        'build_marker': ANALYZER_BUILD_MARKER,
        'app_file': str(Path(__file__).resolve()),
        'app_file_mtime': datetime.fromtimestamp(Path(__file__).stat().st_mtime, tz=UTC).isoformat(),
        'storage_layout': {
            'static': str(storage.static_dir.resolve()),
            'runtime': str(storage.runtime_dir.resolve()),
            'derived': str(storage.derived_dir.resolve()),
            'sqlite': health.db_path,
        },
        'storage': {
            'backend': health.backend,
            'single_writer': health.single_writer,
            'retention_days': health.retention_days,
            'max_runtime_events_per_project': health.max_runtime_events_per_project,
        },
    }



@app.get('/llm/probe')
def llm_probe(model: str | None = Query(default=None)):
    settings = get_provider_settings_from_env()
    client = build_enrichment_client_from_env()
    probe = client.probe(model=model) if hasattr(client, 'probe') else {
        'status': 'unsupported',
        'configured': settings.configured,
        'provider_name': settings.provider_name,
        'requested_model': model or settings.default_model,
    }
    return {
        **probe,
        'configured': settings.configured,
        'provider_credentials_configured': settings.configured,
        'provider_probe_status': probe.get('status', 'unknown'),
        'base_url': settings.base_url,
        'default_model': settings.default_model,
        'fallback_model': settings.fallback_model,
        'provider_name': settings.provider_name,
    }


@app.post('/derived/{project_name}/{doc_key}')
def write_derived_doc(project_name: str, doc_key: str, payload: dict[str, object]):
    _get_storage().write_derived(project_name, doc_key, payload)
    return {'status': 'ok', 'project_name': project_name, 'doc_key': doc_key}


@app.get('/derived/{project_name}/{doc_key}')
def get_derived_doc(project_name: str, doc_key: str):
    payload = _get_storage().load_derived(project_name, doc_key)
    if payload is None:
        raise HTTPException(status_code=404, detail=f'Missing derived doc for {project_name}/{doc_key}')
    return payload


@app.get('/derived/{project_name}')
def list_derived_docs(project_name: str, prefix: str | None = Query(default=None)):
    return {'items': _get_storage().list_derived(project_name, prefix=prefix)}


def _build_provider() -> tuple[object, ModuleEnrichmentProvider]:
    settings = get_provider_settings_from_env()
    if not settings.configured:
        raise HTTPException(status_code=400, detail=_provider_not_configured_detail(settings))
    return settings, build_enrichment_client_from_env()


@app.post('/llm/analyze/project/{project_name}')
def llm_analyze_project(
    project_name: str,
    model: str | None = Query(default=None),
    cheap_mode: bool = Query(default=False),
):
    settings, client = _build_provider()
    schema = _load_schema(project_name)
    selected_model = model or (settings.fallback_model if cheap_mode else settings.default_model)
    try:
        analysis = client.analyze_project_schema(schema, model=selected_model)
    except Exception as exc:
        logger.warning('Project LLM analysis degraded', exc_info=True, extra={'project_name': project_name})
        analysis = LLMProjectAnalysis(
            project_name=schema.project_name,
            llm_model=selected_model,
            llm_provider=settings.provider_name,
            degraded=True,
            warnings=[f'LLM request failed: {type(exc).__name__}: {exc}'],
        )
    _get_storage().write_derived(project_name, 'llm_project', analysis.model_dump(mode='json'))
    return analysis.model_dump(mode='json')


@app.post('/llm/analyze/module/{project_name}')
def llm_analyze_module(
    project_name: str,
    module_path: str = Query(..., description='Python module path, for example billing.api.handlers'),
    model: str | None = Query(default=None),
    cheap_mode: bool = Query(default=False),
):
    settings, client = _build_provider()
    schema = _load_schema(project_name)
    module = next((item for item in schema.modules if item.module_path == module_path), None)
    if module is None:
        raise HTTPException(status_code=404, detail=f'Module not found: {module_path}')

    runtime_symbol_counts = {
        symbol.qualified_name: symbol.runtime_call_count
        for symbol in schema.symbols
        if symbol.module_path == module_path and symbol.runtime_call_count > 0
    }
    inbound_dependencies = sorted(
        {
            edge.source
            for edge in schema.edges
            if edge.kind == 'import' and edge.target == module_path
        }
    )
    selected_model = model or (settings.fallback_model if cheap_mode else settings.default_model)
    try:
        analysis = client.analyze_module(
            module,
            runtime_symbol_counts=runtime_symbol_counts,
            inbound_dependencies=inbound_dependencies,
            model=selected_model,
        )
    except Exception as exc:
        logger.warning(
            'Module LLM analysis degraded',
            exc_info=True,
            extra={'project_name': project_name, 'module_path': module_path},
        )
        analysis = LLMModuleAnalysis(
            module_path=module.module_path,
            llm_model=selected_model,
            llm_provider=settings.provider_name,
            degraded=True,
            warnings=[f'LLM request failed: {type(exc).__name__}: {exc}'],
        )

    safe_module_name = module_path.replace('/', '_').replace('.', '__')
    _get_storage().write_derived(project_name, f'llm_module_{safe_module_name}', analysis.model_dump(mode='json'))
    return analysis.model_dump(mode='json')


@app.get('/ops/status/{project_name}')
def project_ops_status(project_name: str):
    storage = _get_storage()
    schema = None
    try:
        schema = _load_schema(project_name)
    except HTTPException:
        schema = None
    derived_items = storage.list_derived(project_name)
    latest_updated = max((item.get('updated_at') for item in derived_items if item.get('updated_at')), default=None)
    return {
        'project_name': project_name,
        'schema_ready': schema is not None,
        'module_count': schema.module_count if schema is not None else 0,
        'runtime_event_count': schema.runtime_event_count if schema is not None else 0,
        'derived_docs_count': len(derived_items),
        'latest_derived_updated_at': latest_updated,
        'storage': asdict(_get_storage().health()),
    }


@app.get('/report/{project_name}')
def project_report(project_name: str):
    storage = _get_storage()
    schema = _load_schema(project_name)
    provider_status = llm_status()
    derived_items = storage.list_derived(project_name)
    latest_updated = max((item.get('updated_at') for item in derived_items if item.get('updated_at')), default=None)
    ops_status = {
        'project_name': project_name,
        'schema_ready': True,
        'module_count': schema.module_count,
        'runtime_event_count': schema.runtime_event_count,
        'derived_docs_count': len(derived_items),
        'latest_derived_updated_at': latest_updated,
        'storage': asdict(storage.health()),
    }
    scan_summary = storage.load_derived(project_name, 'ops_project_scan_summary') or {}
    live_pass_summary = storage.load_derived(project_name, 'ops_live_pass_summary') or {}
    live_pass_summary = {
        'llm_status': provider_status,
        **live_pass_summary,
    }
    return compose_project_report(
        schema,
        ops_status=ops_status,
        scan_summary=scan_summary,
        live_pass_summary=live_pass_summary,
        derived_items=derived_items,
        analyzer_url=scan_summary.get('analyzer_url') if isinstance(scan_summary, dict) else None,
    )
