from __future__ import annotations


FREE_TEXT_TRANSLATIONS_RU = {
    "Treat this as an active path and verify changes with runtime evidence.": "Считай этот модуль активным путём и проверяй изменения по runtime-доказательствам.",
    "Add a short module docstring or contract note.": "Добавь короткий docstring модуля или contract note.",
    "Review cleanup candidates manually before deleting symbols.": "Проверь cleanup-кандидаты вручную перед удалением символов.",
    "Defer work here unless this module re-enters a live path.": "Не трогай этот модуль, пока он снова не войдёт в живой путь.",
    "Review the module-analysis output before relying on it.": "Проверь вывод module-analysis вручную, прежде чем на него опираться.",
    "Add one real runtime flow to confirm the live path.": "Добавь один реальный runtime flow, чтобы подтвердить живой путь.",
    "public surface normalized to top-level API": "публичная поверхность нормализована до верхнеуровневого API",
    "cleanup suggestions were narrowed": "cleanup-подсказки были сужены",
    "runtime hotspots normalized to observed symbols": "runtime hotspots нормализованы к наблюдаемым символам",
    "dependencies filtered to static imports": "зависимости отфильтрованы до статических импортов",
    "purpose derived from module signal": "назначение выведено из сигнала модуля",
    "responsibilities normalized to grounded bullets": "ответственности нормализованы до опорных пунктов",
    "semantic signal remains low": "семантический сигнал остаётся слабым",
    "no runtime evidence": "нет runtime-доказательств",
    "missing module docstring": "у модуля нет docstring",
    "public surface may be noisy": "публичная поверхность может быть шумной",
    "cleanup suggestions need manual review": "cleanup-подсказки требуют ручной проверки",
    "Publishes BIOS status updates derived from configuration and runtime health state.": "Публикует обновления BIOS-статуса, выведенные из конфигурации и runtime-состояния здоровья.",
    "Coordinates one q-core agent tick across agent, FSM, and state-store steps.": "Координирует один тик q-core агента через шаги agent, FSM и state-store.",
    "Transforms BIOS status inputs into ship health reports and subsystem diagnostics.": "Преобразует входы BIOS-статуса в отчёты о здоровье корабля и диагностику подсистем.",
    "Publish live runtime status updates for the active module flow.": "Публикует живые обновления runtime-статуса для активного потока модуля.",
    "Build status and component payloads from module state and configuration.": "Собирает status и component payloads из состояния модуля и конфигурации.",
    "Reload runtime configuration used by the module.": "Перезагружает runtime-конфигурацию, используемую модулем.",
    "Run one agent tick through the module's sync and async entrypoints.": "Проводит один тик агента через sync и async entrypoints модуля.",
    "Coordinate FSM and state-store handling during tick execution.": "Координирует обработку FSM и state-store во время исполнения тика.",
    "Validate and normalize BIOS status inputs into internal health structures.": "Проверяет и нормализует входы BIOS-статуса во внутренние структуры здоровья.",
    "Build BIOS reports used by downstream health evaluation.": "Собирает BIOS-отчёты, используемые downstream-оценкой здоровья.",
    "Derive subsystem diagnostics from BIOS report data.": "Выводит диагностику подсистем из данных BIOS-отчёта.",
}


UI_TEXT = {
    "en": {
        "app_subtitle": "Module operations console",
        "operator_dashboard_unavailable": "Operator overview: no run/operator state loaded",
        "operator_dashboard_header": "Operator overview\nProject: {project_name}\nRun: {run_id} | mode: {run_mode}\nOverall: {run_status}",
        "operator_dashboard_layers": "Layers: structure={factual} | execution={runtime}\nAnalysis={enrichment} | report={report}",
        "operator_dashboard_modules": "Modules: total={module_count} | extra analysis done={enriched_count} | with limitations={degraded_count} | routes={route_count} | env vars={env_count}",
        "operator_dashboard_artifacts": "Artifacts: total={artifacts_total} | missing={artifacts_missing} | stale={artifacts_stale}",
        "operator_dashboard_warnings": "Limitations: {warnings}",
        "operator_dashboard_next_step": "Next safe step: {next_step}",
        "operator_health_title": "Data readiness:",
        "operator_health_unavailable": "Data readiness: operator state unavailable",
        "operator_health_card": "{layer}: {status}\n  {detail}",
        "operator_health_warnings": "Limitations={count}: {warnings}",
        "operator_health_no_warnings": "Limitations=0",
        "operator_project_status_ready": "ready",
        "operator_project_status_limited": "partly ready",
        "operator_layer_factual_ready": "structure ready",
        "operator_layer_factual_error": "scan errors found",
        "operator_layer_runtime_ready": "execution data collected",
        "operator_layer_runtime_absent": "execution data not collected",
        "operator_layer_enrichment_ready": "extra analysis ready",
        "operator_layer_enrichment_absent": "extra analysis not run",
        "operator_layer_enrichment_degraded": "extra analysis limited",
        "operator_layer_enrichment_failed": "extra analysis failed",
        "operator_layer_report_ready": "report built",
        "operator_layer_report_absent": "report not built",
        "operator_layer_name_factual": "Structure",
        "operator_layer_name_runtime": "Execution data",
        "operator_layer_name_enrichment": "Extra analysis",
        "operator_layer_name_report": "Report",
        "operator_layer_status_ready": "ready",
        "operator_layer_status_absent": "no data",
        "operator_layer_status_degraded": "limited",
        "operator_layer_status_failed": "failed",
        "operator_health_detail_factual": "modules checked={modules_scanned} | scan errors={scan_errors}",
        "operator_health_detail_runtime": "runtime events={runtime_event_count}",
        "operator_health_detail_enrichment": "{provider} | analyzed={modules_done} | limited={degraded_count}",
        "operator_health_detail_report": "report reference={report_ref}",
        "operator_limit_runtime_absent": "execution data missing",
        "operator_limit_enrichment_absent": "extra analysis missing",
        "operator_limit_enrichment_degraded": "extra analysis limited",
        "operator_limit_provider_unconfigured": "analysis source not configured",
        "operator_provider_configured": "source configured",
        "operator_provider_not_configured": "source not configured",
        "operator_artifacts_present": "artifacts present",
        "operator_artifacts_absent": "artifacts missing",
        "operator_artifacts_limited": "artifacts limited",
        "operator_probe_ok": "source checked",
        "operator_probe_failed": "source check failed",
        "operator_probe_not_checked": "source not checked",
        "operator_next_collect_runtime": "collect real runtime evidence before runtime-behavior claims",
        "operator_next_run_enrichment": "run extra analysis for selected scope",
        "operator_module_table_unavailable": "module_table: operator state unavailable",
        "operator_module_table_header": "  Module                                     State             Limits                    Findings Action",
        "operator_module_table_col_selected": "Sel",
        "operator_module_table_col_module": "Module",
        "operator_module_table_col_state": "State",
        "operator_module_table_col_limits": "Limits",
        "operator_module_table_col_findings": "Findings",
        "operator_module_table_col_action": "Action",
        "operator_module_table_row": "{marker} {module_path:<42} {state:<16} {limits:<25} {findings:<8} {action}",
        "operator_module_state_ready": "ready",
        "operator_module_state_limited": "partly ready",
        "operator_module_state_warning": "warning",
        "operator_module_state_error": "error",
        "operator_module_state_absent": "no data",
        "operator_module_state_unknown": "unknown",
        "operator_module_limits_none": "none",
        "operator_module_limits_runtime": "no runtime",
        "operator_module_limits_enrichment": "no extra analysis",
        "operator_module_limits_runtime_and_enrichment": "no runtime, no extra analysis",
        "operator_module_action_none": "no action needed",
        "operator_module_action_collect_runtime": "collect runtime",
        "operator_module_action_run_enrichment": "run extra analysis",
        "operator_module_action_review_findings": "review findings",
        "operator_module_table_more": "... {hidden_count} more modules hidden",
        "operator_module_table_empty": "module_table: no modules",
        "operator_inspector_title": "Module card:",
        "operator_inspector_unavailable": "inspector: operator state unavailable",
        "operator_inspector_no_selection": "select a module to inspect factual signals, enrichment state, and artifact evidence",
        "operator_inspector_missing_module": "selected module is not in operator state: {module_path}",
        "operator_inspector_module": "module={module_path}",
        "operator_inspector_source": "file={file_path}",
        "operator_inspector_signals": "signals={signals}",
        "operator_inspector_enrichment": "extra analysis={analysis_state} | limitation={limit_state} | findings={findings}",
        "operator_action_log_title": "action_log:",
        "operator_action_log_recent_title": "recent_actions:",
        "operator_action_log_empty": "- no actions yet",
        "operator_action_log_line": "- {action}: {state}",
        "operator_action_log_history_line": "- {timestamp} | {action}: {state} | {message}",
        "operator_action_log_hotkeys": "hotkeys: r refresh | g scan | p enrichment queue | a enrich selected | / search | t RU/EN | ctrl+q quit",
        "tooltip_operator_dashboard": "Operator dashboard assembled from OperatorState; read-only summary of current run and analyzer-backed state.",
        "tooltip_operator_health_cards": "Layer health cards for factual, runtime, enrichment, and report state.",
        "tooltip_operator_inspector": "Selected-module inspector based on factual scanner signals and enrichment state.",
        "tooltip_operator_action_log": "Recent operator actions, running actions, and keyboard shortcuts.",
        "lang_button": "RU/EN (t): EN",
        "overview_tab": "Overview",
        "explorer_tab": "Module Explorer",
        "runtime_tab": "Execution",
        "replay_tab": "Data Check",
        "analysis_guide_tab": "Analysis Guide",
        "analysis_guide_kicker": "read-only operator checklist | scroll for full pass order",
        "analysis_guide_body": """ANALYSIS GUIDE
Read this as an operator checklist.
The tab does not run anything; it explains what each layer can prove.

01  ANALYZER-BACKED SCAN
Do: scan through the analyzer path, not offline-only.
You get: schema, module list, counts, storage status, analyzer health.
Check: schema_ready=true, modules_count>0, storage paths visible.
Boundary: static facts; no semantic module purpose.

02  RUN PACKAGE
Do: `project-introspector run` for the exact source root.
Artifacts: run_result.json, summary.json, schema.json,
           static_snapshot.json, progress.log.
You get: factual/runtime/enrichment/report/limits status.
Boundary: evidence package; not QIKI canon or architecture truth.

03  EXPORT REPORT
Do: `project-introspector report` after run artifacts exist.
You get: factual counts, limits, module findings, provenance.
Check: project report and module findings panels reload cleanly.
Boundary: evidence summary; not command authority.

04  TUI REFRESH / RELOAD
Do: refresh status, refresh views, reload analyzer/report.
You get: current schema, table, cards, storage, report, findings.
Check: scanned_at, freshness, schema_ready, module counts, limits.
Boundary: reload reads artifacts; it does not create new analysis.

05  SIGNAL FILTERS
Use: routes / entrypoints, env-config, missing enrichment,
     degraded, has-findings, module search.
Act from: candidates for inspection, not final importance.
Boundary: filters are triage only.

06  RUNTIME EVENTS
Do: run only existing instrumented paths or ready live examples.
You get: runtime event counts and runtime-linked modules.
Check: runtime_events, runtime_modules, runtime_merged.
Boundary: no instrumentation means no runtime proof.

07  VALIDATION RESULT
Do: validate produced artifacts.
You get: pass/fail plus missing or malformed artifact warnings.
Act from: fix artifact shape before trusting the report view.
Boundary: validation checks shape; it adds no new code knowledge.

NOT AVAILABLE WITHOUT LLM OR CODE CHANGES
- normal semantic description of module responsibility
- ownership-boundary or architecture conclusions
- QIKI canon, board state, or runtime-truth understanding
- automatic priority summary of what to fix first

CLEAN PASS ORDER
1. Start analyzer if analyzer-backed state is required.
2. Scan the exact source root.
3. Generate run package.
4. Export report.
5. Validate artifacts.
6. Refresh/reload TUI.
7. Inspect with signal filters and Module Explorer.""",
        "overview_search": "Search module_path",
        "runtime_search": "Search module_path",
        "module_details": "Module details",
        "warnings": "Warnings",
        "processing_notes": "Derivation notes",
        "actionable_hints": "Actionable hints",
        "public_symbols": "Public symbols",
        "responsibilities": "Role in system",
        "btn_refresh_status": "Refresh Status",
        "btn_refresh_views": "Refresh Views",
        "btn_scan_project": "Scan Project",
        "btn_live_pass": "Run Enrichment Queue",
        "btn_reanalyze": "Enrich Selected",
        "btn_confirm_action": "Confirm: {action}",
        "tooltip_lang_button": "Switch the interface language between English and Russian.",
        "tooltip_overview_search": "Filter the overview table by module_path.",
        "tooltip_runtime_search": "Filter the runtime table by module_path.",
        "tooltip_refresh_status": "Reload /llm/status and refresh the analyzer health panel.",
        "tooltip_scan_project": "Requires confirmation. Re-run the non-LLM static scan and upload a fresh schema snapshot.",
        "tooltip_live_pass": "Requires confirmation. Run provider-backed enrichment for the baseline queue modules without re-running factual scan.",
        "tooltip_live_pass_unavailable": "Unavailable: provider is not configured; factual scan remains available.",
        "tooltip_reanalyze": "Requires confirmation. Run provider-backed enrichment for the currently selected module.",
        "tooltip_reanalyze_unavailable": "Unavailable: provider is not configured; factual scan remains available.",
        "tooltip_module_summary": "Primary module card: purpose, status, degraded flag, and source path.",
        "tooltip_module_warnings": "Warnings gathered for the selected module.",
        "tooltip_module_notes": "Derivation notes that explain how the current module summary was produced.",
        "tooltip_module_hints": "Operator-facing follow-up suggestions for the selected module.",
        "tooltip_module_public": "Public entrypoints and symbols exposed by the selected module.",
        "tooltip_module_responsibilities": "System role breakdown for the selected module.",
        "tooltip_module_artifacts": "Provenance and freshness for the detail artifact currently shown.",
        "tooltip_project_report": "Read-only project report: factual counts first, runtime limits explicit, enrichment clearly separated.",
        "tooltip_project_findings": "Filtered module findings from the project report. Evidence only; not command authority.",
        "tooltip_replay_actions": "Live state of factual scan, enrichment queue, and selected-module enrichment actions.",
        "tooltip_replay_status": "Separate factual-layer readiness from enrichment-layer/provider state.",
        "tooltip_replay_storage": "Storage locations used by the analyzer.",
        "tooltip_replay_last_pass": "Latest factual scan summary plus latest enrichment queue artifacts.",
        "provider_action_required": "provider-backed action unavailable: provider is not configured; factual scan remains available",
        "provider_actions_status": "provider_actions: {state}",
        "provider_actions_enabled": "available",
        "provider_actions_disabled": "unavailable",
        "provider_action_reason": "provider_action_reason: {reason}",
        "provider_action_reason_configured": "provider is configured",
        "provider_action_reason_not_configured": "provider is not configured; factual scan remains available",
        "provider_action_hint": "operator_hint: {hint}",
        "provider_action_hint_configured": "enrichment actions can run; verify factual scan first",
        "provider_action_hint_not_configured": "run factual scan only or configure provider before enrichment",
        "action_states": "action_states:",
        "action_state_line": "- {label}: {state}",
        "action_idle": "idle",
        "action_running": "running",
        "action_failed": "failed: {message}",
        "action_done": "done",
        "action_confirmed": "confirmed; running on next step",
        "action_confirmation_cancelled": "confirmation cancelled",
        "action_confirmation_required": "confirmation_required: {message}",
        "confirmation_cancelled": "Confirmation cancelled. No action was started.",
        "confirm_scan_project": "Confirm Scan Project: reruns factual scan for the configured source root and uploads schema/report state to analyzer. Press/click the same action again to start.",
        "confirm_live_pass": "Confirm Enrichment Queue: calls the configured provider and writes semantic artifacts for the representative module queue. Press/click the same action again to start.",
        "confirm_reanalyze": "Confirm Enrich Selected: calls the provider for module {module_path} and writes a new module artifact. Press/click the same action again to start.",
        "refreshing_all": "Refreshing analyzer status, schema, and derived module views...",
        "running_project_scan": "Running non-LLM project scan and schema upload...",
        "reloading_status": "Reloading /llm/status...",
        "running_live_pass": "Running provider-backed enrichment queue...",
        "live_pass_finished": "enrichment queue finished",
        "select_module": "Select a module before re-analysis.",
        "reanalyzing": "Re-analyzing {module_path} ...",
        "action_in_progress": "{label} is already running",
        "analyzer_error": "analyzer error: {message}",
        "storage_unavailable": "storage: unavailable",
        "live_pass_unavailable": "live pass: unavailable",
        "summary_line": "project={project_name} | modules={module_count} | modules with runtime={runtime_count}\nscan={scan_state} | analysis source={enrichment_state} | artifacts ready={enrichment_done} | artifacts missing={enrichment_pending} | limited={enrichment_degraded}",
        "summary_scan_available": "schema_loaded",
        "summary_enrichment_available": "configured",
        "summary_enrichment_waiting_provider": "unconfigured",
        "compact_provider_action_unavailable": "unavailable: provider not configured",
        "operator_next": "operator_next: {step}",
        "operator_next_scan_first": "run factual scan first",
        "operator_next_review_scan": "review factual scan counts, then enrich if needed",
        "operator_next_configure_provider": "factual scan is ready; configure provider before enrichment",
        "operator_next_run_enrichment_queue": "run enrichment queue or enrich selected module",
        "operator_next_review_enrichment": "review enriched module evidence and freshness",
        "overview_filter_all": "All",
        "overview_filter_needs-attention": "Needs attention",
        "overview_filter_missing-enrichment": "No extra analysis",
        "overview_filter_has-findings": "Has findings",
        "overview_filter_routes": "Routes / entrypoints",
        "overview_filter_env-config": "Env/config",
        "overview_controls": "Show={status_filter} | only limited={degraded_only} | only warnings={warnings_only}",
        "runtime_controls": "Runtime view={runtime_filter}",
        "replay_status": "factual_layer:\n- schema_ready: {schema_ready}\n- runtime_merged: {runtime_merged}\n- modules_count: {module_count}\n- runtime_modules: {runtime_count}\n- last_scan_status: {scan_status}\n\nenrichment_layer:\n- provider_actions: {provider_actions}\n- queue_status: {enrichment_status}\n- semantic_artifacts_absent: {enrichment_pending}\n- semantic_artifacts_done: {enrichment_done}\n- semantic_degraded: {enrichment_degraded}\n- modules_failed: {enrichment_failed}\n- default_model: {default_model}\n- fallback_model: {fallback_model}\n\nanalyzer:\n- app_name: {app_name}\n- build_marker: {build_marker}",
        "scan_status": "factual_scan: {status}\nmodules_scanned: {modules_scanned}\nscan_errors: {scan_errors}\nruntime_events: {runtime_event_count}\nscanned_at: {scanned_at}",
        "project_scan_summary": "factual_scan_summary: {summary_path}\nstatus: {status}\nsource_root: {source_root}\nmodules_scanned: {modules_scanned}\nscan_errors: {scan_errors}\nruntime_events: {runtime_event_count}\nscanned_at: {scanned_at}\noutput_dir: {output_dir}",
        "project_scan_unavailable": "project scan: unavailable",
        "replay_summary": "enrichment_summary: {summary_path}\nllm_status: {status_path}\nqueue_status: {queue_status}\nprovider_configured: {provider_configured}\nmodules_requested: {modules_requested}\nmodules_done: {modules_done}\nmodules_degraded: {modules_degraded}\nmodules_failed: {modules_failed}\noutput_dir: {output_dir}",
        "storage_line": "{name}: {path}",
        "artifact_line": "artifact: {path}",
        "artifact_meta": "source={source_kind} | variant={variant} | updated_at={updated_at}",
        "module_path": "module_path: {module_path}",
        "source_path": "source_path: {file_path}",
        "no_module_selected": "No module selected.",
        "semantic_unavailable": "semantic_output: unavailable",
        "purpose": "purpose: {purpose}",
        "status": "status: {status}",
        "enrichment_state": "enrichment: {state}",
        "degraded": "degraded: {degraded}",
        "enrichment_state_value_pending": "pending",
        "enrichment_state_value_running": "running",
        "enrichment_state_value_done": "done",
        "enrichment_state_value_degraded": "degraded",
        "status_value_active": "active",
        "status_value_stale-risk": "stale-risk",
        "status_value_low-signal": "low-signal",
        "status_value_no-analysis": "no semantic analysis",
        "bool_true": "true",
        "bool_false": "false",
        "none_list": "{title}:\n- none",
        "detail_unavailable": "semantic module detail is unavailable because enrichment artifact is absent",
        "empty_sections": "empty semantic sections: {sections}",
        "source": "source: {file_path}",
        "detail_source": "detail_source: {source_kind}",
        "detail_variant": "detail_variant: {variant}",
        "detail_updated_at": "detail_updated_at: {updated_at}",
        "artifact": "artifact: {artifact_path}",
        "artifact_freshness": "freshness: {state} | scan_at={scan_updated_at}",
        "evidence_reason": "evidence_reason: {reason}",
        "operator_hint": "operator_hint: {hint}",
        "artifact_exists": "artifact_exists: {artifact_exists}",
        "related_artifacts": "related_artifacts:",
        "source_kind_derived": "derived",
        "source_kind_live-replay": "enrichment-replay",
        "source_kind_live-derived-api": "derived-api",
        "variant_unknown": "unknown",
        "variant_normal": "normal",
        "variant_cheap": "cheap",
        "variant_override": "override",
        "variant_empty": "empty",
        "artifact_freshness_value_current": "current",
        "artifact_freshness_value_stale": "stale",
        "artifact_freshness_value_unknown": "unknown",
        "artifact_freshness_value_missing": "missing",
        "artifact_freshness_value_future_timestamp": "future timestamp",
        "artifact_freshness_value_invalid_timestamp": "invalid timestamp",
        "evidence_reason_value_artifact_missing": "artifact is absent",
        "evidence_reason_value_artifact_timestamp_missing": "artifact timestamp is missing",
        "evidence_reason_value_scan_timestamp_missing": "scan timestamp is missing",
        "evidence_reason_value_timestamp_unparseable": "artifact or scan timestamp is unparseable",
        "evidence_reason_value_artifact_older_than_scan": "artifact timestamp is older than scan timestamp",
        "evidence_reason_value_artifact_at_or_after_scan": "artifact timestamp is at or after scan timestamp",
        "evidence_reason_value_artifact_timestamp_in_future": "artifact timestamp is unexpectedly in the future",
        "operator_hint_value_artifact_missing": "Open the artifact path or rerun enrichment if the file is expected.",
        "operator_hint_value_artifact_timestamp_missing": "Check artifact metadata before comparing it with the scan timestamp.",
        "operator_hint_value_scan_timestamp_missing": "Run or load a factual scan with scanned_at before comparing timestamps.",
        "operator_hint_value_timestamp_unparseable": "Check timestamp formatting in artifact metadata and scan summary.",
        "operator_hint_value_artifact_older_than_scan": "Artifact predates the scan; rerun enrichment if scan-aligned evidence is needed.",
        "operator_hint_value_artifact_at_or_after_scan": "Artifact timestamp is not older than the scan timestamp.",
        "artifact_unavailable": "artifact: unavailable",
        "project_report_unavailable": "project report: unavailable",
        "project_report_summary_block": "Report snapshot: {project_name}\nSource root: {source_root}\nStructure: modules={modules_scanned} | scan errors={scan_errors} | code objects={symbol_count} | import links={import_edge_count}\nExecution data: {runtime_status} | events={runtime_event_count}\nExtra analysis: {enrichment_status} | {provider_configured}\nSource check: {provider_probe} | {enrichment_artifacts}\nLimitations: {limits}\nNext step: {next_safe_step}",
        "project_report_block": "Project report:\n- project: {project_name}\n- source: {source_root}\n\nStructural scan:\n- modules checked: {modules_scanned}\n- scan errors: {scan_errors}\n- functions/classes/symbols: {function_count}/{class_count}/{symbol_count}\n- import edges: {import_edge_count}\n\nExecution data:\n- state: {runtime_status}\n- events: {runtime_event_count}\n\nExtra analysis:\n- state: {enrichment_status}\n- source: {provider_configured}\n- source check: {provider_probe}\n- artifacts: {enrichment_artifacts}\n- modules analyzed/limited/failed: {modules_done}/{modules_degraded}/{modules_failed}\n- module findings: {module_findings_total}\nModule findings preview:\n{module_findings_preview}\n\nLimitations: {limits}\nLLM is truth source: {llm_truth}\nNext safe steps:\n{next_safe_steps}",
        "project_report_finding_line": "- {module_path} | status={status} | degraded={degraded} | warnings={warnings_count} | source={source}",
        "project_findings_block": "Module findings: {visible_total}/{total_count}\n{findings}",
        "project_findings_detail_line": "- {module_path}\n  status={status} | degraded={degraded} | warnings={warnings_count}\n  purpose={purpose}\n  warning_preview={warning_preview}\n  hint_preview={hint_preview}\n  provenance={source} | trust_layer={trust_layer}",
        "project_findings_more": "- ... {remaining} more findings hidden by display limit",
        "none": "none",
        "unknown": "unknown",
        "unknown_error": "unknown error",
        "scan_status_value_done": "done",
        "scan_status_value_pending": "pending",
        "scan_status_value_skipped": "skipped",
        "enrichment_queue_status_value_pending": "pending",
        "enrichment_queue_status_value_done": "done",
        "enrichment_queue_status_value_degraded": "degraded",
        "enrichment_queue_status_value_failed": "failed",
    },
    "ru": {
        "app_subtitle": "Операционная консоль модулей",
        "operator_dashboard_unavailable": "Сводка: run/operator state не загружен",
        "operator_dashboard_header": "Сводка\nПроект: {project_name}\nЗапуск: {run_id} | режим: {run_mode}\nИтог: {run_status}",
        "operator_dashboard_layers": "Слои: структура={factual} | исполнение={runtime}\nАнализ={enrichment} | отчёт={report}",
        "operator_dashboard_modules": "Модули: всего={module_count} | доп. анализ готов={enriched_count} | с ограничениями={degraded_count} | маршруты={route_count} | env-настройки={env_count}",
        "operator_dashboard_artifacts": "Артефакты: всего={artifacts_total} | отсутствуют={artifacts_missing} | устарели={artifacts_stale}",
        "operator_dashboard_warnings": "Ограничения: {warnings}",
        "operator_dashboard_next_step": "Следующий безопасный шаг: {next_step}",
        "operator_health_title": "Готовность данных:",
        "operator_health_unavailable": "Готовность данных: operator state недоступен",
        "operator_health_card": "{layer}: {status}\n  {detail}",
        "operator_health_warnings": "Ограничения={count}: {warnings}",
        "operator_health_no_warnings": "Ограничения=0",
        "operator_project_status_ready": "готово",
        "operator_project_status_limited": "частично готово",
        "operator_layer_factual_ready": "структура готова",
        "operator_layer_factual_error": "есть ошибки сканирования",
        "operator_layer_runtime_ready": "данные исполнения собраны",
        "operator_layer_runtime_absent": "данные исполнения не собраны",
        "operator_layer_enrichment_ready": "доп. анализ готов",
        "operator_layer_enrichment_absent": "доп. анализ не запускался",
        "operator_layer_enrichment_degraded": "доп. анализ ограничен",
        "operator_layer_enrichment_failed": "доп. анализ завершился ошибкой",
        "operator_layer_report_ready": "отчёт собран",
        "operator_layer_report_absent": "отчёт не собран",
        "operator_layer_name_factual": "Структура",
        "operator_layer_name_runtime": "Данные исполнения",
        "operator_layer_name_enrichment": "Доп. анализ",
        "operator_layer_name_report": "Отчёт",
        "operator_layer_status_ready": "готово",
        "operator_layer_status_absent": "нет данных",
        "operator_layer_status_degraded": "ограничено",
        "operator_layer_status_failed": "ошибка",
        "operator_health_detail_factual": "модулей проверено={modules_scanned} | ошибок сканирования={scan_errors}",
        "operator_health_detail_runtime": "событий исполнения={runtime_event_count}",
        "operator_health_detail_enrichment": "{provider} | обработано={modules_done} | ограничено={degraded_count}",
        "operator_health_detail_report": "снимок отчёта={report_ref}",
        "operator_limit_runtime_absent": "нет данных исполнения",
        "operator_limit_enrichment_absent": "нет доп. анализа",
        "operator_limit_enrichment_degraded": "доп. анализ ограничен",
        "operator_limit_provider_unconfigured": "источник анализа не настроен",
        "operator_provider_configured": "источник настроен",
        "operator_provider_not_configured": "источник не настроен",
        "operator_artifacts_present": "артефакты есть",
        "operator_artifacts_absent": "артефактов нет",
        "operator_artifacts_limited": "артефакты ограничены",
        "operator_probe_ok": "источник проверен",
        "operator_probe_failed": "проверка источника не прошла",
        "operator_probe_not_checked": "источник не проверен",
        "operator_next_collect_runtime": "собрать реальные данные исполнения перед выводами о поведении",
        "operator_next_run_enrichment": "запустить доп. анализ для выбранной области",
        "operator_module_table_unavailable": "таблица модулей: состояние оператора недоступно",
        "operator_module_table_header": "  Модуль                                     Состояние        Ограничения              Проблемы Действие",
        "operator_module_table_col_selected": "Выб",
        "operator_module_table_col_module": "Модуль",
        "operator_module_table_col_state": "Состояние",
        "operator_module_table_col_limits": "Ограничения",
        "operator_module_table_col_findings": "Находки",
        "operator_module_table_col_action": "Действие",
        "operator_module_table_row": "{marker} {module_path:<42} {state:<16} {limits:<25} {findings:<8} {action}",
        "operator_module_state_ready": "готово",
        "operator_module_state_limited": "частично готово",
        "operator_module_state_warning": "предупреждение",
        "operator_module_state_error": "ошибка",
        "operator_module_state_absent": "нет данных",
        "operator_module_state_unknown": "неизвестно",
        "operator_module_limits_none": "нет",
        "operator_module_limits_runtime": "нет исполнения",
        "operator_module_limits_enrichment": "нет доп. анализа",
        "operator_module_limits_runtime_and_enrichment": "нет исполнения, нет доп. анализа",
        "operator_module_action_none": "действий не требуется",
        "operator_module_action_collect_runtime": "собрать исполнение",
        "operator_module_action_run_enrichment": "запустить доп. анализ",
        "operator_module_action_review_findings": "разобрать проблемы",
        "operator_module_table_more": "... ещё скрыто модулей: {hidden_count}",
        "operator_module_table_empty": "таблица_модулей: модулей нет",
        "operator_inspector_title": "Карточка модуля:",
        "operator_inspector_unavailable": "инспектор: состояние оператора недоступно",
        "operator_inspector_no_selection": "выберите модуль, чтобы увидеть структурные сигналы, доп. анализ и артефакты",
        "operator_inspector_missing_module": "выбранного модуля нет в состоянии оператора: {module_path}",
        "operator_inspector_module": "модуль={module_path}",
        "operator_inspector_source": "файл={file_path}",
        "operator_inspector_signals": "сигналы={signals}",
        "operator_inspector_enrichment": "доп. анализ={analysis_state} | ограничение={limit_state} | проблемы={findings}",
        "operator_action_log_title": "журнал_действий:",
        "operator_action_log_recent_title": "последние_действия:",
        "operator_action_log_empty": "- действий пока нет",
        "operator_action_log_line": "- {action}: {state}",
        "operator_action_log_history_line": "- {timestamp} | {action}: {state} | {message}",
        "operator_action_log_hotkeys": "горячие клавиши: r обновить | g скан | p очередь доп. анализа | a анализ модуля | / поиск | t RU/EN | ctrl+q выход",
        "tooltip_operator_dashboard": "Сводка оператора по текущему запуску и данным analyzer.",
        "tooltip_operator_health_cards": "Состояние слоёв: структура, исполнение, доп. анализ и отчёт.",
        "tooltip_operator_inspector": "Инспектор выбранного модуля по структурным сигналам и доп. анализу.",
        "tooltip_operator_action_log": "Последние действия оператора, выполняемые действия и горячие клавиши.",
        "lang_button": "RU/EN (t): RU",
        "overview_tab": "Обзор",
        "explorer_tab": "Модуль",
        "runtime_tab": "Исполнение",
        "replay_tab": "Проверка данных",
        "analysis_guide_tab": "Гайд анализа",
        "analysis_guide_kicker": "read-only operator checklist | прокрутка покажет полный порядок прохода",
        "analysis_guide_body": """ГАЙД АНАЛИЗА
Это операторский чеклист.
Вкладка ничего не запускает; она показывает, что доказывает каждый слой.

01  ANALYZER-BACKED SCAN
Сделай: scan через analyzer, не offline-only.
Увидишь: schema, список модулей, counts, storage, здоровье analyzer.
Проверь: schema_ready=true, modules_count>0, storage paths видны.
Граница: static facts; смысл модуля не выводится.

02  RUN PACKAGE
Сделай: `project-introspector run` для точного source root.
Артефакты: run_result.json, summary.json, schema.json,
           static_snapshot.json, progress.log.
Увидишь: статусы factual/runtime/enrichment/report/limits.
Граница: пакет evidence; не QIKI canon и не architecture truth.

03  EXPORT REPORT
Сделай: `project-introspector report` после run artifacts.
Увидишь: factual counts, limits, module findings, provenance.
Проверь: project report и module findings обновились без ошибок.
Граница: evidence summary; не command authority.

04  TUI REFRESH / RELOAD
Сделай: refresh status, refresh views, reload analyzer/report.
Увидишь: текущие schema, table, cards, storage, report, findings.
Проверь: scanned_at, freshness, schema_ready, module counts, limits.
Граница: reload читает artifacts; новый анализ не создаёт.

05  SIGNAL FILTERS
Используй: routes / entrypoints, env-config, missing enrichment,
           degraded, has-findings, module search.
Действуй от: кандидатов на инспекцию, не от финальной важности.
Граница: filters - только triage.

06  RUNTIME EVENTS
Сделай: запускай только уже instrumented paths или live examples.
Увидишь: runtime event counts и runtime-linked modules.
Проверь: runtime_events, runtime_modules, runtime_merged.
Граница: нет instrumentation - нет runtime proof.

07  VALIDATION RESULT
Сделай: validate produced artifacts.
Увидишь: pass/fail и missing/malformed artifact warnings.
Действуй от: сначала чини форму artifacts, потом доверяй report view.
Граница: validation проверяет форму; новых знаний о коде не даёт.

БЕЗ LLM ИЛИ ДОРАБОТКИ НЕЛЬЗЯ ПОЛУЧИТЬ
- нормальное описание ответственности модуля
- выводы уровня ownership boundary / architecture
- понимание QIKI canon, board state или runtime truth
- автоматический приоритет, что чинить первым

ЧИСТЫЙ ПОРЯДОК ПРОХОДА
1. Запустить analyzer, если нужен analyzer-backed state.
2. Просканировать точный source root.
3. Собрать run package.
4. Экспортировать report.
5. Провалидировать artifacts.
6. Обновить/reload TUI.
7. Инспектировать через signal filters и Module Explorer.""",
        "overview_search": "Поиск по пути модуля",
        "runtime_search": "Поиск по пути модуля",
        "module_details": "Карточка модуля",
        "warnings": "Предупреждения",
        "processing_notes": "Как получен вывод",
        "actionable_hints": "Практические подсказки",
        "public_symbols": "Публичные символы",
        "responsibilities": "Роль в системе",
        "btn_refresh_status": "Обновить статус",
        "btn_refresh_views": "Обновить представления",
        "btn_scan_project": "Сканировать проект",
        "btn_live_pass": "Запустить enrichment queue",
        "btn_reanalyze": "Обогатить модуль",
        "btn_confirm_action": "Подтвердить: {action}",
        "tooltip_lang_button": "Переключает язык интерфейса между русским и английским.",
        "tooltip_overview_search": "Фильтрует таблицу обзора по пути модуля.",
        "tooltip_runtime_search": "Фильтрует таблицу рантайма по пути модуля.",
        "tooltip_refresh_status": "Перечитывает /llm/status и обновляет панель здоровья анализатора.",
        "tooltip_scan_project": "Требует подтверждения. Перезапускает не-LLM static scan и загружает свежий schema snapshot.",
        "tooltip_live_pass": "Требует подтверждения. Запускает provider-backed enrichment для очереди модулей без повторного factual scan.",
        "tooltip_live_pass_unavailable": "Недоступно: provider не настроен; factual scan остаётся доступен.",
        "tooltip_reanalyze": "Требует подтверждения. Запускает provider-backed enrichment для выбранного модуля.",
        "tooltip_reanalyze_unavailable": "Недоступно: provider не настроен; factual scan остаётся доступен.",
        "tooltip_module_summary": "Главная карточка модуля: purpose, status, degraded и путь к исходнику.",
        "tooltip_module_warnings": "Предупреждения по выбранному модулю.",
        "tooltip_module_notes": "Поясняет, как был получен текущий вывод по модулю.",
        "tooltip_module_hints": "Следующие шаги для оператора по выбранному модулю.",
        "tooltip_module_public": "Публичные точки входа и символы выбранного модуля.",
        "tooltip_module_responsibilities": "Роль выбранного модуля в системе.",
        "tooltip_module_artifacts": "Источник и свежесть detail artifact, который сейчас показан.",
        "tooltip_project_report": "Read-only отчёт проекта: сначала factual counts, runtime limits явно, enrichment отдельно.",
        "tooltip_project_findings": "Фильтрованные module findings из отчёта проекта. Только evidence, не command authority.",
        "tooltip_replay_actions": "Текущее состояние factual scan, enrichment queue и enrichment выбранного модуля.",
        "tooltip_replay_status": "Отдельно показывает готовность factual-слоя и состояние enrichment/provider.",
        "tooltip_replay_storage": "Пути storage, которые использует анализатор.",
        "tooltip_replay_last_pass": "Сводка последнего factual scan и артефакты последней enrichment queue.",
        "provider_action_required": "provider-backed действие недоступно: provider не настроен; factual scan остаётся доступен",
        "provider_actions_status": "provider_actions: {state}",
        "provider_actions_enabled": "доступны",
        "provider_actions_disabled": "недоступны",
        "provider_action_reason": "причина_доступности_enrichment: {reason}",
        "provider_action_reason_configured": "provider настроен",
        "provider_action_reason_not_configured": "provider не настроен; factual scan остаётся доступен",
        "provider_action_hint": "следующий_шаг: {hint}",
        "provider_action_hint_configured": "enrichment-действия можно запускать; сначала проверь factual scan",
        "provider_action_hint_not_configured": "запускай только factual scan или настрой provider перед enrichment",
        "action_states": "Состояние действий:",
        "action_state_line": "- {label}: {state}",
        "action_idle": "ожидание",
        "action_running": "выполняется",
        "action_failed": "ошибка: {message}",
        "action_done": "завершено",
        "action_confirmed": "подтверждено; запускаю действие",
        "action_confirmation_cancelled": "подтверждение отменено",
        "action_confirmation_required": "требуется_подтверждение: {message}",
        "confirmation_cancelled": "Подтверждение отменено. Действие не запускалось.",
        "confirm_scan_project": "Подтвердите Scan Project: заново запускает factual scan для настроенного source root и загружает schema/report state в analyzer. Нажмите это же действие ещё раз для старта.",
        "confirm_live_pass": "Подтвердите Enrichment Queue: вызывает настроенный provider и записывает semantic artifacts для очереди модулей. Нажмите это же действие ещё раз для старта.",
        "confirm_reanalyze": "Подтвердите Enrich Selected: вызывает provider для модуля {module_path} и записывает новый module artifact. Нажмите это же действие ещё раз для старта.",
        "refreshing_all": "Обновляю status анализатора, schema и derived-представление модулей...",
        "running_project_scan": "Запускаю не-LLM скан проекта и загрузку схемы...",
        "reloading_status": "Перечитываю /llm/status...",
        "running_live_pass": "Запускаю provider-backed enrichment queue...",
        "live_pass_finished": "enrichment queue завершена",
        "select_module": "Сначала выберите модуль.",
        "reanalyzing": "Переанализирую {module_path} ...",
        "action_in_progress": "{label} уже выполняется",
        "analyzer_error": "ошибка анализатора: {message}",
        "storage_unavailable": "storage: недоступен",
        "live_pass_unavailable": "replay: недоступен",
        "summary_line": "проект={project_name} | модулей={module_count} | с данными исполнения={runtime_count}\nскан={scan_state} | источник анализа={enrichment_state} | артефакты готовы={enrichment_done} | артефакты отсутствуют={enrichment_pending} | ограничены={enrichment_degraded}",
        "summary_scan_available": "schema_loaded",
        "summary_enrichment_available": "configured",
        "summary_enrichment_waiting_provider": "unconfigured",
        "compact_provider_action_unavailable": "недоступно: provider не настроен",
        "operator_next": "следующий_шаг: {step}",
        "operator_next_scan_first": "сначала запусти factual scan",
        "operator_next_review_scan": "проверь factual counts, потом запускай enrichment при необходимости",
        "operator_next_configure_provider": "factual scan готов; настрой provider перед enrichment",
        "operator_next_run_enrichment_queue": "запусти очередь enrichment или обогащение выбранного модуля",
        "operator_next_review_enrichment": "проверь evidence и свежесть обогащённых модулей",
        "overview_filter_all": "Все",
        "overview_filter_needs-attention": "Требуют внимания",
        "overview_filter_missing-enrichment": "Без доп. анализа",
        "overview_filter_has-findings": "С проблемами",
        "overview_filter_routes": "Маршруты / entrypoints",
        "overview_filter_env-config": "Env/config",
        "overview_controls": "Показать={status_filter} | только с ограничениями={degraded_only} | только предупреждения={warnings_only}",
        "runtime_controls": "Runtime view={runtime_filter}",
        "replay_status": "factual_layer:\n- schema_ready: {schema_ready}\n- runtime_merged: {runtime_merged}\n- modules_count: {module_count}\n- runtime_modules: {runtime_count}\n- last_scan_status: {scan_status}\n\nenrichment_layer:\n- provider_actions: {provider_actions}\n- queue_status: {enrichment_status}\n- semantic_artifacts_absent: {enrichment_pending}\n- semantic_artifacts_done: {enrichment_done}\n- semantic_degraded: {enrichment_degraded}\n- modules_failed: {enrichment_failed}\n- default_model: {default_model}\n- fallback_model: {fallback_model}\n\nanalyzer:\n- app_name: {app_name}\n- build_marker: {build_marker}",
        "scan_status": "factual_scan: {status}\nmodules_scanned: {modules_scanned}\nscan_errors: {scan_errors}\nruntime_events: {runtime_event_count}\nscanned_at: {scanned_at}",
        "project_scan_summary": "factual_scan_summary: {summary_path}\nstatus: {status}\nsource_root: {source_root}\nmodules_scanned: {modules_scanned}\nscan_errors: {scan_errors}\nruntime_events: {runtime_event_count}\nscanned_at: {scanned_at}\noutput_dir: {output_dir}",
        "project_scan_unavailable": "project scan: недоступен",
        "replay_summary": "enrichment_summary: {summary_path}\nllm_status: {status_path}\nqueue_status: {queue_status}\nprovider_configured: {provider_configured}\nmodules_requested: {modules_requested}\nmodules_done: {modules_done}\nmodules_degraded: {modules_degraded}\nmodules_failed: {modules_failed}\nкаталог_вывода: {output_dir}",
        "storage_line": "{name}: {path}",
        "artifact_line": "артефакт: {path}",
        "artifact_meta": "источник={source_kind} | вариант={variant} | обновлено={updated_at}",
        "module_path": "путь_модуля: {module_path}",
        "source_path": "путь_исходника: {file_path}",
        "no_module_selected": "Модуль не выбран.",
        "semantic_unavailable": "семантический_вывод: недоступен",
        "purpose": "назначение: {purpose}",
        "status": "статус: {status}",
        "enrichment_state": "обогащение: {state}",
        "degraded": "деградация: {degraded}",
        "enrichment_state_value_pending": "ожидает",
        "enrichment_state_value_running": "выполняется",
        "enrichment_state_value_done": "готово",
        "enrichment_state_value_degraded": "деградировано",
        "status_value_active": "активен",
        "status_value_stale-risk": "риск устаревания",
        "status_value_low-signal": "мало сигнала",
        "status_value_no-analysis": "без semantic анализа",
        "bool_true": "да",
        "bool_false": "нет",
        "none_list": "{title}:\n- нет",
        "detail_unavailable": "semantic-детали недоступны: enrichment artifact отсутствует",
        "empty_sections": "пустые смысловые секции: {sections}",
        "source": "источник: {file_path}",
        "detail_source": "источник_деталей: {source_kind}",
        "detail_variant": "вариант_деталей: {variant}",
        "detail_updated_at": "обновлено_деталей: {updated_at}",
        "artifact": "артефакт: {artifact_path}",
        "artifact_freshness": "свежесть: {state} | scan_at={scan_updated_at}",
        "evidence_reason": "причина_evidence: {reason}",
        "operator_hint": "подсказка_оператору: {hint}",
        "artifact_exists": "артефакт_существует: {artifact_exists}",
        "related_artifacts": "связанные_артефакты:",
        "source_kind_derived": "производный",
        "source_kind_live-replay": "enrichment-replay",
        "source_kind_live-derived-api": "derived-api",
        "variant_unknown": "неизвестно",
        "variant_normal": "обычный",
        "variant_cheap": "дешёвый",
        "variant_override": "override",
        "variant_empty": "пустой",
        "artifact_freshness_value_current": "актуален",
        "artifact_freshness_value_stale": "устарел",
        "artifact_freshness_value_unknown": "неизвестно",
        "artifact_freshness_value_missing": "отсутствует",
        "artifact_freshness_value_future_timestamp": "timestamp из будущего",
        "artifact_freshness_value_invalid_timestamp": "некорректный timestamp",
        "evidence_reason_value_artifact_missing": "артефакт отсутствует",
        "evidence_reason_value_artifact_timestamp_missing": "timestamp артефакта отсутствует",
        "evidence_reason_value_scan_timestamp_missing": "timestamp скана отсутствует",
        "evidence_reason_value_timestamp_unparseable": "timestamp артефакта или скана не читается",
        "evidence_reason_value_artifact_older_than_scan": "timestamp артефакта старше timestamp скана",
        "evidence_reason_value_artifact_at_or_after_scan": "timestamp артефакта не старше timestamp скана",
        "evidence_reason_value_artifact_timestamp_in_future": "timestamp артефакта неожиданно находится в будущем",
        "operator_hint_value_artifact_missing": "Открой путь артефакта или перезапусти enrichment, если файл ожидается.",
        "operator_hint_value_artifact_timestamp_missing": "Проверь metadata артефакта перед сравнением с timestamp скана.",
        "operator_hint_value_scan_timestamp_missing": "Запусти или загрузи factual scan со scanned_at перед сравнением timestamp.",
        "operator_hint_value_timestamp_unparseable": "Проверь формат timestamp в metadata артефакта и summary скана.",
        "operator_hint_value_artifact_older_than_scan": "Артефакт старше скана; перезапусти enrichment, если нужен evidence под этот scan.",
        "operator_hint_value_artifact_at_or_after_scan": "Timestamp артефакта не старше timestamp скана.",
        "operator_hint_value_artifact_timestamp_in_future": "Проверь системное время или metadata артефакта перед доверием freshness.",
        "artifact_unavailable": "артефакт: недоступен",
        "project_report_unavailable": "отчёт проекта: недоступен",
        "project_report_summary_block": "Снимок отчёта: {project_name}\nКорень кода: {source_root}\nСтруктура: модулей={modules_scanned} | ошибок={scan_errors} | объектов кода={symbol_count} | связей import={import_edge_count}\nДанные исполнения: {runtime_status} | событий={runtime_event_count}\nДоп. анализ: {enrichment_status} | {provider_configured}\nПроверка источника: {provider_probe} | {enrichment_artifacts}\nОграничения: {limits}\nСледующий шаг: {next_safe_step}",
        "project_report_block": "Отчёт проекта:\n- проект: {project_name}\n- source: {source_root}\n\nСтруктурный анализ:\n- модулей проверено: {modules_scanned}\n- ошибок сканирования: {scan_errors}\n- functions/classes/symbols: {function_count}/{class_count}/{symbol_count}\n- import edges: {import_edge_count}\n\nДанные исполнения:\n- состояние: {runtime_status}\n- событий: {runtime_event_count}\n\nДоп. анализ:\n- состояние: {enrichment_status}\n- источник: {provider_configured}\n- проверка источника: {provider_probe}\n- артефакты: {enrichment_artifacts}\n- модулей обработано/с ограничениями/с ошибкой: {modules_done}/{modules_degraded}/{modules_failed}\n- проблем по модулям: {module_findings_total}\nПревью проблем:\n{module_findings_preview}\n\nОграничения: {limits}\nLLM является источником истины: {llm_truth}\nСледующие безопасные шаги:\n{next_safe_steps}",
        "project_report_finding_line": "- {module_path} | статус={status} | деградация={degraded} | warnings={warnings_count} | источник={source}",
        "project_findings_block": "Проблемы по модулям: {visible_total}/{total_count}\n{findings}",
        "project_findings_detail_line": "- {module_path}\n  статус={status} | деградация={degraded} | warnings={warnings_count}\n  назначение={purpose}\n  warning_preview={warning_preview}\n  hint_preview={hint_preview}\n  provenance={source} | trust_layer={trust_layer}",
        "project_findings_more": "- ... скрыто ещё {remaining} findings из-за лимита отображения",
        "none": "нет",
        "unknown": "неизвестно",
        "unknown_error": "неизвестная ошибка",
        "scan_status_value_done": "готово",
        "scan_status_value_pending": "ожидает",
        "scan_status_value_skipped": "пропущен",
        "enrichment_queue_status_value_pending": "ожидает",
        "enrichment_queue_status_value_done": "готово",
        "enrichment_queue_status_value_degraded": "деградировано",
        "enrichment_queue_status_value_failed": "ошибка",
    },
}


def tui_text(language: str, key: str, **kwargs: object) -> str:
    template = UI_TEXT[language][key]
    return template.format(**kwargs) if kwargs else template


SEMANTIC_TEXT_BY_CODE = {
    "warning": {
        "semantic_signal": {"en": "semantic signal remains low", "ru": "семантический сигнал остаётся слабым"},
        "runtime_signal": {"en": "no runtime evidence", "ru": "нет runtime-доказательств"},
        "docstring": {"en": "missing module docstring", "ru": "у модуля нет docstring"},
        "public_surface": {"en": "public surface may be noisy", "ru": "публичная поверхность может быть шумной"},
        "cleanup": {"en": "cleanup suggestions need manual review", "ru": "cleanup-подсказки требуют ручной проверки"},
        "schema_mismatch": {
            "en": "LLM response did not match the expected analysis schema.",
            "ru": "Ответ LLM не совпал с ожидаемой схемой анализа.",
        },
    },
    "processing_note": {
        "public_surface": {"en": "public surface normalized to top-level API", "ru": "публичная поверхность нормализована до верхнеуровневого API"},
        "cleanup": {"en": "cleanup suggestions were narrowed", "ru": "cleanup-подсказки были сужены"},
        "runtime_hotspots": {"en": "runtime hotspots normalized to observed symbols", "ru": "runtime hotspots нормализованы к наблюдаемым символам"},
        "dependencies": {"en": "dependencies filtered to static imports", "ru": "зависимости отфильтрованы до статических импортов"},
        "purpose": {"en": "purpose derived from module signal", "ru": "назначение выведено из сигнала модуля"},
        "responsibilities": {"en": "responsibilities normalized to grounded bullets", "ru": "ответственности нормализованы до опорных пунктов"},
    },
    "actionable_hint": {
        "review_output": {"en": "Review the module-analysis output before relying on it.", "ru": "Проверь вывод module-analysis вручную, прежде чем на него опираться."},
        "add_runtime_flow": {"en": "Add one real runtime flow to confirm the live path.", "ru": "Добавь один реальный runtime flow, чтобы подтвердить живой путь."},
        "verify_active_path": {"en": "Treat this as an active path and verify changes with runtime evidence.", "ru": "Считай этот модуль активным путём и проверяй изменения по runtime-доказательствам."},
        "add_docstring": {"en": "Add a short module docstring or contract note.", "ru": "Добавь короткий docstring модуля или contract note."},
        "keep_surface_compact": {"en": "Keep the public surface compact and avoid helper leakage.", "ru": "Держи публичную поверхность компактной и не допускай утечки helper-символов."},
        "review_cleanup": {"en": "Review cleanup candidates manually before deleting symbols.", "ru": "Проверь cleanup-кандидаты вручную перед удалением символов."},
        "defer_until_live": {"en": "Defer work here unless this module re-enters a live path.", "ru": "Не трогай этот модуль, пока он снова не войдёт в живой путь."},
    },
    "purpose": {},
    "responsibility": {
        "resp.generic.process_inputs": {"en": "Process module-specific inputs into structured results.", "ru": "Обрабатывает входы, специфичные для модуля, в структурированные результаты."},
        "resp.generic.handle_step": {"en": "Handle one explicit module workflow step.", "ru": "Обрабатывает один явный шаг workflow модуля."},
        "resp.generic.run_main_workflow": {"en": "Run the main workflow exposed by this module.", "ru": "Запускает основной workflow, который экспортирует этот модуль."},
    },
}


def _dynamic_semantic_text(language: str, kind: str, code: str) -> str | None:
    payload = code.split(':', 1)[1] if ':' in code else ''
    if kind == 'purpose' and code.startswith('purpose.generic.publish_updates:'):
        return (
            f'Publishes {payload} updates for the surrounding runtime flow.'
            if language == 'en'
            else f'Публикует обновления {payload} для окружающего runtime-потока.'
        )
    if kind == 'purpose' and code.startswith('purpose.generic.process_inputs:'):
        return (
            f'Processes {payload} inputs into module-specific results.'
            if language == 'en'
            else f'Обрабатывает входы {payload} в результаты, специфичные для модуля.'
        )
    if kind == 'purpose' and code.startswith('purpose.generic.run_workflow:'):
        return (
            f'Runs the {payload} workflow for this module.'
            if language == 'en'
            else f'Запускает workflow {payload} для этого модуля.'
        )
    if kind == 'purpose' and code.startswith('purpose.generic.coordinate_entrypoint:'):
        return (
            f'Coordinates the {payload} entrypoint for this module.'
            if language == 'en'
            else f'Координирует entrypoint {payload} для этого модуля.'
        )
    if kind == 'responsibility' and code.startswith('resp.generic.implement_main_workflow:'):
        return (
            f'Implement the main {payload} workflow exposed by this module.'
            if language == 'en'
            else f'Реализует основной workflow {payload}, который экспортирует этот модуль.'
        )
    return None


def localize_semantic_text(language: str, value: str, *, code: str | None = None, kind: str | None = None) -> str:
    if language == 'en':
        if code and kind:
            exact = SEMANTIC_TEXT_BY_CODE.get(kind, {}).get(code)
            if exact is not None:
                return exact['en']
            dynamic = _dynamic_semantic_text(language, kind, code)
            if dynamic is not None:
                return dynamic
        return value
    if code and kind:
        exact = SEMANTIC_TEXT_BY_CODE.get(kind, {}).get(code)
        if exact is not None:
            return exact['ru']
        dynamic = _dynamic_semantic_text(language, kind, code)
        if dynamic is not None:
            return dynamic
    return localize_free_text(language, value)


def localize_semantic_list(language: str, values: list[str], *, codes: list[str] | None = None, kind: str | None = None) -> list[str]:
    localized: list[str] = []
    for index, value in enumerate(values):
        code = codes[index] if codes and index < len(codes) else None
        localized.append(localize_semantic_text(language, value, code=code, kind=kind))
    return localized


def localize_free_text(language: str, value: str) -> str:
    if language != "ru":
        return value
    translated = FREE_TEXT_TRANSLATIONS_RU.get(value)
    if translated is not None:
        return translated
    if value.startswith("high semantic drift: "):
        return "сильный семантический дрейф: " + value.removeprefix("high semantic drift: ")
    if value.startswith("Publishes ") and value.endswith(" updates for the surrounding runtime flow."):
        topic = value.removeprefix("Publishes ").removesuffix(" updates for the surrounding runtime flow.")
        return f"Публикует обновления {topic} для окружающего runtime-потока."
    if value.startswith("Processes ") and value.endswith(" inputs into module-specific results."):
        topic = value.removeprefix("Processes ").removesuffix(" inputs into module-specific results.")
        return f"Обрабатывает входы {topic} в результаты, специфичные для модуля."
    if value.startswith("Runs the ") and value.endswith(" workflow for this module."):
        topic = value.removeprefix("Runs the ").removesuffix(" workflow for this module.")
        return f"Запускает workflow {topic} для этого модуля."
    if value.startswith("Coordinates the ") and value.endswith(" entrypoint for this module."):
        topic = value.removeprefix("Coordinates the ").removesuffix(" entrypoint for this module.")
        return f"Координирует entrypoint {topic} для этого модуля."
    if value.startswith("Implement the main ") and value.endswith(" workflow exposed by this module."):
        topic = value.removeprefix("Implement the main ").removesuffix(" workflow exposed by this module.")
        return f"Реализует основной workflow {topic}, который экспортирует этот модуль."
    return value
