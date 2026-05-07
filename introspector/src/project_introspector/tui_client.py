from __future__ import annotations

import json
import os
import subprocess
import sys
from hashlib import blake2b
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic

import httpx

from .artifact_resolver import ArtifactCandidate, ArtifactCandidates, resolve_module_artifact
from .models import LLMModuleAnalysis, ProjectSchema
from .operator_state import OperatorState, discover_latest_run_dir, build_operator_state
from .tui_models import (
    AnalyzerStatus,
    ArtifactReference,
    LivePassSummary,
    ModuleAnalysisArtifact,
    ProjectScanSummary,
    SubprocessResult,
)


def _default_source_root(introspector_root: Path) -> Path:
    candidates = [introspector_root / "src", introspector_root.parent / "src"]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return introspector_root / "src"


class IntrospectorTuiClient:
    def __init__(
        self,
        *,
        analyzer_url: str = "http://127.0.0.1:8015",
        project_name: str = "INTROSPECTOR_DEMO",
        introspector_root: Path | None = None,
        source_root: str | Path | None = None,
        python_bin: str | None = None,
        timeout: float = 30.0,
        cache_ttl: float = 2.0,
        runs_root: str | Path | None = None,
    ) -> None:
        self.analyzer_url = analyzer_url.rstrip("/")
        self.project_name = project_name
        self.introspector_root = introspector_root or Path(__file__).resolve().parents[2]
        self.source_root = Path(
            source_root or os.getenv("INTROSPECTOR_SOURCE_ROOT") or _default_source_root(self.introspector_root)
        ).resolve()
        self.python_bin = python_bin or os.getenv("PYTHON_BIN") or sys.executable
        self.timeout = timeout
        self.cache_ttl = cache_ttl
        self.runs_root = Path(runs_root or os.getenv("INTROSPECTOR_RUNS_ROOT") or (self.introspector_root / "tmp" / "release_runs")).resolve()
        self._status_cache: tuple[float, AnalyzerStatus] | None = None
        self._schema_cache: tuple[float, ProjectSchema] | None = None
        self._live_pass_cache: tuple[tuple[bool, int | None, int | None], LivePassSummary] | None = None
        self._project_scan_cache: tuple[tuple[bool, int | None, int | None], ProjectScanSummary] | None = None
        self._derived_doc_cache: dict[str, tuple[float, dict[str, object] | None]] = {}
        self._missing_derived_docs: set[str] = set()
        self._derived_doc_index_cache: dict[str, tuple[float, set[str] | None]] = {}
        self._report_cache: tuple[float, dict[str, object] | None] | None = None
        self._artifact_cache: dict[
            tuple[str, str],
            tuple[
                tuple[
                    tuple[bool, int | None, int | None],
                    tuple[tuple[str, str, str, str | None, bool], ...],
                ],
                ModuleAnalysisArtifact,
            ],
        ] = {}
        self._operator_state_cache: tuple[tuple[bool, int | None, int | None, str | None], OperatorState | None] | None = None

    @classmethod
    def from_env(cls) -> "IntrospectorTuiClient":
        return cls(
            analyzer_url=os.getenv("INTROSPECTOR_ANALYZER_URL", "http://127.0.0.1:8015"),
            project_name=os.getenv("INTROSPECTOR_PROJECT_NAME", "INTROSPECTOR_DEMO"),
            source_root=os.getenv("INTROSPECTOR_SOURCE_ROOT"),
            python_bin=os.getenv("PYTHON_BIN"),
            runs_root=os.getenv("INTROSPECTOR_RUNS_ROOT"),
        )

    def fetch_status(self, *, force: bool = False) -> AnalyzerStatus:
        if not force and self._status_cache is not None and self._cache_alive(self._status_cache[0]):
            return self._status_cache[1]
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(f"{self.analyzer_url}/llm/status")
            response.raise_for_status()
        status = AnalyzerStatus(**response.json())
        self._status_cache = (monotonic(), status)
        return status

    def fetch_schema(self, *, force: bool = False) -> ProjectSchema:
        if not force and self._schema_cache is not None and self._cache_alive(self._schema_cache[0]):
            return self._schema_cache[1]
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(f"{self.analyzer_url}/schema/{self.project_name}")
            response.raise_for_status()
        schema = ProjectSchema.model_validate(response.json())
        self._schema_cache = (monotonic(), schema)
        return schema


    def fetch_report(self, *, force: bool = False) -> dict[str, object] | None:
        if not force and self._report_cache is not None and self._cache_alive(self._report_cache[0]):
            return self._report_cache[1]
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(f"{self.analyzer_url}/report/{self.project_name}")
        except httpx.HTTPError:
            self._report_cache = (monotonic(), None)
            return None
        if response.status_code == 404:
            self._report_cache = (monotonic(), None)
            return None
        response.raise_for_status()
        payload = response.json()
        self._report_cache = (monotonic(), payload)
        return payload

    def fetch_module_analysis(self, module_path: str, *, cheap_mode: bool = False) -> LLMModuleAnalysis:
        params = {"module_path": module_path}
        if cheap_mode:
            params["cheap_mode"] = "true"
        with httpx.Client(timeout=max(self.timeout, 120.0)) as client:
            response = client.post(
                f"{self.analyzer_url}/llm/analyze/module/{self.project_name}",
                params=params,
            )
            response.raise_for_status()
        return LLMModuleAnalysis.model_validate(response.json())

    def fetch_derived_doc(self, doc_key: str, *, force: bool = False) -> dict[str, object] | None:
        cached = self._derived_doc_cache.get(doc_key)
        if not force and cached is not None and self._cache_alive(cached[0]):
            return cached[1]
        if not force and doc_key in self._missing_derived_docs:
            return None
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(f"{self.analyzer_url}/derived/{self.project_name}/{doc_key}")
        except httpx.HTTPError:
            self._derived_doc_cache[doc_key] = (monotonic(), None)
            self._missing_derived_docs.add(doc_key)
            return None
        if response.status_code == 404:
            self._derived_doc_cache[doc_key] = (monotonic(), None)
            self._missing_derived_docs.add(doc_key)
            return None
        response.raise_for_status()
        payload = response.json()
        self._derived_doc_cache[doc_key] = (monotonic(), payload)
        self._missing_derived_docs.discard(doc_key)
        return payload

    def list_derived_docs(self, *, prefix: str | None = None) -> list[dict[str, object]] | None:
        params = {"prefix": prefix} if prefix else None
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(f"{self.analyzer_url}/derived/{self.project_name}", params=params)
        except httpx.HTTPError:
            return None
        response.raise_for_status()
        payload = response.json()
        return list(payload.get("items", []))

    def run_live_pass(self) -> SubprocessResult:
        script_path = self.introspector_root / "scripts" / "enrich_modules.py"
        command = [
            self.python_bin,
            str(script_path),
            "--analyzer-url",
            self.analyzer_url,
            "--project-name",
            self.project_name,
            "--source-root",
            str(self.source_root),
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=self.introspector_root,
                check=False,
                capture_output=True,
                text=True,
                timeout=max(self.timeout, 180.0),
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode("utf-8", errors="replace")
            stderr = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode("utf-8", errors="replace")
            return SubprocessResult(
                returncode=124,
                stdout=stdout,
                stderr=stderr,
                timed_out=True,
            )
        return SubprocessResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            timed_out=False,
        )

    def run_project_scan(self) -> SubprocessResult:
        script_path = self.introspector_root / "scripts" / "scan_project.py"
        command = [
            self.python_bin,
            str(script_path),
            "--analyzer-url",
            self.analyzer_url,
            "--project-name",
            self.project_name,
            "--source-root",
            str(self.source_root),
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=self.introspector_root,
                check=False,
                capture_output=True,
                text=True,
                timeout=max(self.timeout, 180.0),
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode("utf-8", errors="replace")
            stderr = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode("utf-8", errors="replace")
            return SubprocessResult(returncode=124, stdout=stdout, stderr=stderr, timed_out=True)
        return SubprocessResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            timed_out=False,
        )

    def load_derived_analyses(
        self,
        module_paths: list[str],
        *,
        storage_layout: dict[str, str] | None = None,
        force: bool = False,
    ) -> dict[str, ModuleAnalysisArtifact]:
        results: dict[str, ModuleAnalysisArtifact] = {}
        for module_path in module_paths:
            results[module_path] = self.load_module_artifact(
                module_path,
                storage_layout=storage_layout,
                force=force,
            )
        return results

    def load_module_artifact(
        self,
        module_path: str,
        *,
        storage_layout: dict[str, str] | None = None,
        analysis_override: LLMModuleAnalysis | None = None,
        force: bool = False,
    ) -> ModuleAnalysisArtifact:
        derived_path = self.derived_artifact_path(module_path, storage_layout=storage_layout)
        derived_ref = self._artifact_ref(derived_path, source_kind="derived", variant="unknown")
        summary = self.load_latest_live_pass(force=force)
        live_refs = self._live_refs_for_module(module_path, summary)
        cache_key = (module_path, str(derived_path))
        artifact_signature = (
            self._path_signature(derived_path),
            tuple(
                (str(ref.path), ref.source_kind, ref.variant, ref.updated_at, ref.exists)
                for ref in live_refs
            ),
        )

        if not force and analysis_override is None:
            cached = self._artifact_cache.get(cache_key)
            if cached is not None and cached[0] == artifact_signature:
                return cached[1]

        scan_timestamp = self._latest_scan_timestamp(force=force)
        api_doc_key = f"llm_module_{module_path.replace('/', '_').replace('.', '__')}"
        api_ref = self._artifact_ref(
            Path(f"{api_doc_key}.json"),
            source_kind="live-derived-api",
            variant="unknown",
            exists=False,
            doc_key=api_doc_key,
            module_path=module_path,
        )
        api_analysis = None
        if self._known_derived_doc_exists(api_doc_key, prefix="llm_module_"):
            api_analysis = self._load_analysis_from_api(api_doc_key, force=force)
            if api_analysis is not None:
                api_ref = self._artifact_ref(
                    Path(f"{api_doc_key}.json"),
                    source_kind="live-derived-api",
                    variant="unknown",
                    exists=True,
                    doc_key=api_doc_key,
                    module_path=module_path,
                )

        local_analysis = self._load_analysis_from_path(derived_path)
        preferred_live_refs = self._preferred_live_refs(live_refs)
        live_payloads: list[tuple[ArtifactReference, LLMModuleAnalysis | None]] = [
            (ref, self._load_analysis_from_ref(ref, force=force))
            for ref in preferred_live_refs
        ]

        override_candidate = None
        if analysis_override is not None:
            override_candidate = ArtifactCandidate(
                source="explicit_override",
                path=derived_path,
                updated_at=datetime.now(UTC).isoformat(),
                exists=True,
                payload=analysis_override,
                variant="override",
            )

        resolved = resolve_module_artifact(
            module_path,
            ArtifactCandidates(
                explicit_override=override_candidate,
                local_module_finding=ArtifactCandidate(
                    source="local_module_finding",
                    path=derived_path,
                    updated_at=derived_ref.updated_at,
                    exists=derived_ref.exists,
                    payload=local_analysis,
                    variant=derived_ref.variant,
                ),
                analyzer_derived_doc=ArtifactCandidate(
                    source="analyzer_derived_doc",
                    path=api_ref.path,
                    doc_key=api_doc_key,
                    updated_at=api_ref.updated_at,
                    exists=api_ref.exists,
                    payload=api_analysis,
                    variant=api_ref.variant,
                ),
                live_replay_refs=[
                    ArtifactCandidate(
                        source="live_replay",
                        path=ref.path,
                        doc_key=ref.doc_key,
                        updated_at=ref.updated_at,
                        exists=ref.exists,
                        payload=payload,
                        variant=ref.variant,
                    )
                    for ref, payload in live_payloads
                ],
                empty_placeholder=ArtifactCandidate(
                    source="empty_placeholder",
                    path=derived_path,
                    updated_at=derived_ref.updated_at,
                    exists=derived_ref.exists,
                    variant="empty",
                ),
                scan_timestamp=scan_timestamp,
            ),
        )
        artifact = self._artifact_from_resolution(
            resolved,
            derived_ref=derived_ref,
            api_ref=api_ref,
            live_refs=preferred_live_refs,
        )
        self._artifact_cache[cache_key] = (artifact_signature, artifact)
        return artifact

    def load_latest_operator_state(self, *, force: bool = False) -> OperatorState | None:
        run_dir = discover_latest_run_dir(self.runs_root)
        if run_dir is None:
            self._operator_state_cache = ((False, None, None, None), None)
            return None
        signature = self._summary_signature(run_dir / "run_result.json")
        if not force and self._operator_state_cache is not None and self._operator_state_cache[0] == signature:
            return self._operator_state_cache[1]
        try:
            state = build_operator_state(run_dir)
        except Exception:
            state = None
        self._operator_state_cache = (signature, state)
        return state

    def _latest_scan_timestamp(self, *, force: bool = False) -> str | None:
        try:
            return self.load_latest_project_scan(force=force).scanned_at
        except Exception:
            return None

    def _artifact_from_resolution(
        self,
        resolved,
        *,
        derived_ref: ArtifactReference,
        api_ref: ArtifactReference,
        live_refs: list[ArtifactReference],
    ) -> ModuleAnalysisArtifact:
        analysis = resolved.payload if isinstance(resolved.payload, LLMModuleAnalysis) else None
        detail_ref = self._detail_ref_for_resolution(
            resolved,
            derived_ref=derived_ref,
            api_ref=api_ref,
            live_refs=live_refs,
        )
        if resolved.reason.startswith("live_replay_ref"):
            related_refs = [ref for ref in live_refs if ref.path != detail_ref.path or ref.doc_key != detail_ref.doc_key] + [derived_ref]
        elif resolved.reason == "analyzer_derived_doc":
            related_refs = live_refs + [derived_ref]
        else:
            related_refs = live_refs
        return ModuleAnalysisArtifact(
            analysis=analysis,
            artifact_path=detail_ref.path,
            detail_ref=detail_ref,
            related_refs=related_refs,
        )

    def _detail_ref_for_resolution(
        self,
        resolved,
        *,
        derived_ref: ArtifactReference,
        api_ref: ArtifactReference,
        live_refs: list[ArtifactReference],
    ) -> ArtifactReference:
        if resolved.reason == "analyzer_derived_doc":
            return api_ref
        if resolved.reason.startswith("live_replay_ref"):
            for ref in live_refs:
                if resolved.doc_key and ref.doc_key == resolved.doc_key:
                    return ref
                if resolved.path is not None and ref.path == resolved.path:
                    return ref
        if resolved.reason == "explicit_override":
            return self._artifact_ref(
                derived_ref.path,
                source_kind="derived",
                variant="override",
                updated_at=resolved.freshness.artifact_timestamp if resolved.freshness else derived_ref.updated_at,
                exists=True,
                doc_key=derived_ref.doc_key,
                module_path=derived_ref.module_path,
            )
        return derived_ref

    def load_latest_live_pass(self, *, force: bool = False) -> LivePassSummary:
        output_dir = self.introspector_root / "tmp" / "live_module_pass"
        summary_path = output_dir / "summary.json"
        status_path = output_dir / "llm_status.json"
        summary_signature = self._summary_signature(summary_path)
        if not force and self._live_pass_cache is not None and self._live_pass_cache[0] == summary_signature:
            return self._live_pass_cache[1]

        doc_key = "ops_live_pass_summary"
        derived_force = force and (
            doc_key not in self._missing_derived_docs or summary_path.exists()
        )
        payload = self.fetch_derived_doc(doc_key, force=derived_force)
        if payload is None:
            if not summary_path.exists():
                summary = LivePassSummary(summary_path=summary_path, status_path=status_path)
                self._live_pass_cache = (summary_signature, summary)
                return summary
            try:
                payload = json.loads(summary_path.read_text(encoding="utf-8"))
            except Exception:
                summary = LivePassSummary(summary_path=summary_path, status_path=status_path)
                self._live_pass_cache = (summary_signature, summary)
                return summary

        artifact_paths = [Path(item) for item in payload.get("artifacts", [])]
        artifact_refs: list[ArtifactReference] = []
        for item in payload.get("artifact_docs", []) or []:
            doc_key = str(item.get("doc_key") or "").strip()
            if not doc_key:
                continue
            artifact_refs.append(
                self._artifact_ref(
                    Path(f"{doc_key}.json"),
                    source_kind="live-derived-api",
                    variant=str(item.get("variant") or "unknown"),
                    updated_at=item.get("updated_at"),
                    exists=True,
                    doc_key=doc_key,
                    module_path=item.get("module_path"),
                )
            )
        artifact_refs.extend(
            self._artifact_ref(
                path,
                source_kind="live-replay",
                variant="cheap" if path.stem.endswith("_cheap") else "normal",
            )
            for path in artifact_paths
        )
        enrichment_payload = payload.get("enrichment") or {}
        factual_payload = payload.get("factual_refresh") or {}
        summary = LivePassSummary(
            summary_path=summary_path,
            status_path=status_path,
            artifact_paths=artifact_paths,
            artifact_refs=artifact_refs,
            project_name=payload.get("project_name"),
            output_dir=payload.get("output_dir"),
            provider_configured=enrichment_payload.get("provider_configured"),
            factual_refresh_status=factual_payload.get("status"),
            enrichment_status=enrichment_payload.get("status"),
            modules_requested=int(enrichment_payload.get("modules_requested", 0) or 0),
            modules_done=int(enrichment_payload.get("modules_done", 0) or 0),
            modules_degraded=int(enrichment_payload.get("modules_degraded", 0) or 0),
            modules_failed=int(enrichment_payload.get("modules_failed", 0) or 0),
        )
        self._live_pass_cache = (summary_signature, summary)
        return summary

    def load_latest_project_scan(self, *, force: bool = False) -> ProjectScanSummary:
        output_dir = self.introspector_root / "tmp" / "project_scan"
        summary_path = output_dir / "summary.json"
        summary_signature = self._summary_signature(summary_path)
        if not force and self._project_scan_cache is not None and self._project_scan_cache[0] == summary_signature:
            return self._project_scan_cache[1]

        payload = self.fetch_derived_doc("ops_project_scan_summary", force=force)
        if payload is None:
            if not summary_path.exists():
                summary = ProjectScanSummary(
                    summary_path=summary_path,
                    source_root=str(self.source_root),
                    output_dir=str(output_dir),
                )
                self._project_scan_cache = (summary_signature, summary)
                return summary
            try:
                payload = json.loads(summary_path.read_text(encoding="utf-8"))
            except Exception:
                summary = ProjectScanSummary(
                    summary_path=summary_path,
                    source_root=str(self.source_root),
                    output_dir=str(output_dir),
                )
                self._project_scan_cache = (summary_signature, summary)
                return summary
        summary = ProjectScanSummary(
            summary_path=summary_path,
            project_name=payload.get("project_name"),
            source_root=payload.get("source_root") or str(self.source_root),
            modules_scanned=int(payload.get("modules_scanned", 0) or 0),
            scan_errors=int(payload.get("scan_errors", 0) or 0),
            scanned_at=payload.get("scanned_at"),
            output_dir=payload.get("output_dir"),
            factual_status=(payload.get("factual_layer") or {}).get("status"),
            schema_ready=bool((payload.get("factual_layer") or {}).get("schema_ready")),
            runtime_merged=bool((payload.get("factual_layer") or {}).get("runtime_merged")),
            runtime_event_count=int((payload.get("factual_layer") or {}).get("runtime_event_count", 0) or 0),
        )
        self._project_scan_cache = (summary_signature, summary)
        return summary

    def invalidate_runtime_cache(self) -> None:
        self._status_cache = None
        self._live_pass_cache = None
        self._project_scan_cache = None
        self._report_cache = None
        self._derived_doc_cache.clear()
        self._missing_derived_docs.clear()
        self._derived_doc_index_cache.clear()

    def invalidate_schema_cache(self) -> None:
        self._schema_cache = None
        self._report_cache = None

    def invalidate_artifact_cache(self, module_path: str | None = None) -> None:
        self._report_cache = None
        if module_path is None:
            self._derived_doc_cache.clear()
            self._missing_derived_docs.clear()
            self._derived_doc_index_cache.clear()
            self._artifact_cache.clear()
            self._operator_state_cache = None
            return
        prefix = f"{module_path.replace('/', '_').replace('.', '__')}"
        self._derived_doc_cache = {
            key: value
            for key, value in self._derived_doc_cache.items()
            if key != f"llm_module_{prefix}"
        }
        self._missing_derived_docs.discard(f"llm_module_{prefix}")
        self._derived_doc_index_cache.clear()
        self._artifact_cache = {
            key: value
            for key, value in self._artifact_cache.items()
            if not key[1].endswith(f"{prefix}.json")
        }

    def derived_artifact_path(
        self,
        module_path: str,
        *,
        storage_layout: dict[str, str] | None = None,
    ) -> Path:
        safe_module_name = module_path.replace("/", "_").replace(".", "__")
        return self._derived_root(storage_layout) / f"{self.project_name}.llm_module_{safe_module_name}.json"

    def _derived_root(self, storage_layout: dict[str, str] | None = None) -> Path:
        if storage_layout and storage_layout.get("derived"):
            return Path(storage_layout["derived"])
        return self.introspector_root / "analyzer" / "data" / "derived"

    def _cache_alive(self, created_at: float) -> bool:
        return monotonic() - created_at <= self.cache_ttl

    @staticmethod
    def _path_signature(path: Path) -> tuple[bool, int | None, int | None]:
        if not path.exists():
            return (False, None, None)
        stat = path.stat()
        return (True, stat.st_mtime_ns, stat.st_size)

    @staticmethod
    def _summary_signature(path: Path) -> tuple[bool, int | None, int | None, str | None]:
        if not path.exists():
            return (False, None, None, None)
        payload = path.read_bytes()
        stat = path.stat()
        return (True, stat.st_mtime_ns, stat.st_size, blake2b(payload, digest_size=8).hexdigest())

    def _load_analysis_from_api(self, doc_key: str, *, force: bool = False) -> LLMModuleAnalysis | None:
        payload = self.fetch_derived_doc(doc_key, force=force)
        if payload is None:
            return None
        try:
            return LLMModuleAnalysis.model_validate(payload)
        except Exception:
            return None

    def _known_derived_doc_exists(self, doc_key: str, *, prefix: str | None = None) -> bool:
        cached = self._derived_doc_index_cache.get(prefix or "")
        if cached is None or not self._cache_alive(cached[0]):
            items = self.list_derived_docs(prefix=prefix)
            if items is None:
                self._derived_doc_index_cache[prefix or ""] = (monotonic(), None)
            else:
                known_keys = {str(item.get("doc_key") or "").strip() for item in items}
                known_keys.discard("")
                self._derived_doc_index_cache[prefix or ""] = (monotonic(), known_keys)
            cached = self._derived_doc_index_cache[prefix or ""]
        known_keys = cached[1]
        if known_keys is None:
            return True
        return doc_key in known_keys

    def _load_analysis_from_path(self, path: Path) -> LLMModuleAnalysis | None:
        if not path.exists():
            return None
        try:
            return LLMModuleAnalysis.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _load_analysis_from_ref(self, ref: ArtifactReference, *, force: bool = False) -> LLMModuleAnalysis | None:
        if ref.doc_key:
            return self._load_analysis_from_api(ref.doc_key, force=force)
        return self._load_analysis_from_path(ref.path)

    def _artifact_ref(
        self,
        path: Path,
        *,
        source_kind: str,
        variant: str,
        updated_at: str | None = None,
        exists: bool | None = None,
        doc_key: str | None = None,
        module_path: str | None = None,
    ) -> ArtifactReference:
        if exists is None:
            exists = path.exists()
        resolved_updated_at = updated_at
        if exists and resolved_updated_at is None and path.exists():
            resolved_updated_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()
        return ArtifactReference(
            path=path,
            source_kind=source_kind,
            variant=variant,
            updated_at=resolved_updated_at,
            exists=exists,
            doc_key=doc_key,
            module_path=module_path,
        )

    def _live_refs_for_module(self, module_path: str, summary: LivePassSummary) -> list[ArtifactReference]:
        slug = module_path.split(".")[-1]
        refs = [
            ref
            for ref in summary.artifact_refs
            if ref.module_path == module_path
            or ref.path.stem == slug
            or ref.path.stem == f"{slug}_cheap"
        ]
        return sorted(
            refs,
            key=lambda ref: (
                0 if ref.variant == "normal" else 1,
                ref.updated_at or "",
            ),
        )

    @staticmethod
    def _preferred_live_refs(refs: list[ArtifactReference]) -> list[ArtifactReference]:
        return sorted(
            refs,
            key=lambda ref: (
                0 if ref.variant == "normal" else 1,
                -(1 if ref.updated_at else 0),
                ref.updated_at or "",
            ),
        )
