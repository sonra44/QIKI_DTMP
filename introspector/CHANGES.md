## 2026-04-26 — operational contract realignment

- rechecked the local analyzer and factual scan path against the current tree
- moved the default local analyzer endpoint to `127.0.0.1:8015` across scripts, TUI client defaults, tests, and docs
- aligned `scan_project.py` and `live_module_pass.py` so both default to this tool's own `src` tree
- documented that external project scans must use explicit `--source-root` or `INTROSPECTOR_SOURCE_ROOT`
- restored the local pytest suite after the API-derived TUI client contract gained the `force` keyword
- verified intentional unconfigured-provider enrichment degrades without failing the factual layer
- added deterministic report-quality composer and read-only `GET /report/{project_name}` endpoint
- report v1 exposes factual layer, runtime layer, enrichment layer, module findings, explicit limits, next safe steps, and provenance that marks LLM output as non-authoritative
- wired report v1 into the Textual TUI as a read-only project overview, keeping factual/runtime/enrichment layers visually separated
- added the same read-only report block to the Scan / Enrichment tab and included a compact `module_findings` preview with derived-doc provenance

## 2026-04-04 — next pass: ops API, status axes, documentation realignment

- added analyzer `/derived/...` API for persisted summaries and derived artifacts
- moved TUI module artifacts and replay and project-scan summaries to API-first loading with filesystem fallback
- split module status into backward-compatible axes: `activity_status`, `attention_status`, `runtime_signal_status`, `semantic_confidence_status`
- kept JSON mirrors for compatibility while leaving SQLite as primary analyzer storage
- rewrote baseline documentation to describe the tool as project-neutral and provider-neutral rather than host-project-specific

# Hardened changes

## Immediate stability fixes

- runtime emitter is now fail-open by default and keeps buffered events on failed flush
- instrumentation no longer breaks wrapped business functions when emission fails
- static scanner records parse and read failures in `scan_errors` instead of aborting the whole scan
- analyzer writes JSON stores atomically and validates runtime batches by `project_name`
- analyzer degrades LLM failures into structured `degraded=true` responses instead of surfacing `500`

## LLM improvements

- provider requests try strict JSON Schema output first where supported
- if structured output is rejected by the model or provider, the client falls back to prompt-only JSON mode
- OpenRouter supports model-level failover through `models=[primary, fallback]`
- the provider layer now documents OpenRouter, generic OpenAI-compatible, and Inception or Mercury contours explicitly

## Test coverage added

- scanner survives syntax errors
- emitter retains buffered events after failed flush
- instrumentation remains non-blocking when emitter fails
- runtime ingestion rejects mixed-project batches
- project LLM endpoint returns degraded output on upstream failure

## Final alignment pass

- added semantic codes for `purpose` and `responsibilities` when deterministic repair can classify them
- switched TUI semantic rendering to code-first localization with free-text fallback
- fixed duplicate `warning_codes` field in `LLMModuleAnalysis`
- cleaned remaining Ruff issues and kept the test suite green

## Documentation note

- older handoffs and earlier operational experiments used host-project-specific examples
- current documentation now treats those as historical validation context, not as the canonical identity of `project-introspector`
- canonical docs now describe representative module samples, generic replay behavior, and explicit provider-neutral startup expectations
