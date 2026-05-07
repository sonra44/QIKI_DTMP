from __future__ import annotations

from collections import Counter

from .models import DependencyEdge, ProjectSchema, RuntimeEvent, StaticScanEnvelope, SymbolSummary


def build_schema(snapshot: StaticScanEnvelope, runtime_events: list[RuntimeEvent] | None = None) -> ProjectSchema:
    runtime_events = runtime_events or []
    edges: dict[tuple[str, str, str], DependencyEdge] = {}

    for module in snapshot.modules:
        import_targets = [
            fact.normalized_import
            for fact in getattr(module, 'import_facts', [])
            if fact.normalized_import
        ] or module.imports
        for imported in import_targets:
            key = (module.module_path, imported, "import")
            edges[key] = DependencyEdge(source=module.module_path, target=imported, kind="import")

    runtime_counts = Counter(event.qualified_name for event in runtime_events if event.event_type == "call")
    runtime_modules = Counter(event.module_path for event in runtime_events if event.event_type == "call")

    for event in runtime_events:
        if event.event_type != "call":
            continue
        key = ("runtime", event.module_path, "runtime_call")
        if key not in edges:
            edges[key] = DependencyEdge(
                source="runtime",
                target=event.module_path,
                kind="runtime_call",
                weight=0,
            )
        edges[key].weight += 1

    symbols: list[SymbolSummary] = []
    function_count = 0
    class_count = 0
    notes: list[str] = []

    for scan_error in snapshot.scan_errors:
        notes.append(
            f"Scan error in {scan_error.module_path or scan_error.file_path}: "
            f"{scan_error.error_type}: {scan_error.message}"
        )

    for module in snapshot.modules:
        if runtime_modules[module.module_path] == 0:
            notes.append(f"No runtime events seen yet for module: {module.module_path}")
        for function in module.functions:
            function_count += 1
            symbols.append(
                SymbolSummary(
                    qualified_name=function.qualified_name,
                    symbol_type="function",
                    module_path=module.module_path,
                    runtime_call_count=runtime_counts[function.qualified_name],
                    has_docstring=bool(function.docstring),
                )
            )
        for klass in module.classes:
            class_count += 1
            symbols.append(
                SymbolSummary(
                    qualified_name=klass.qualified_name,
                    symbol_type="class",
                    module_path=module.module_path,
                    runtime_call_count=0,
                    has_docstring=bool(klass.docstring),
                )
            )
            for method in klass.methods:
                function_count += 1
                symbols.append(
                    SymbolSummary(
                        qualified_name=method.qualified_name,
                        symbol_type="function",
                        module_path=module.module_path,
                        runtime_call_count=runtime_counts[method.qualified_name],
                        has_docstring=bool(method.docstring),
                    )
                )

    deduped_notes = list(dict.fromkeys(notes))
    return ProjectSchema(
        project_name=snapshot.project_name,
        module_count=len(snapshot.modules),
        function_count=function_count,
        class_count=class_count,
        runtime_event_count=len(runtime_events),
        modules=snapshot.modules,
        edges=list(edges.values()),
        symbols=sorted(symbols, key=lambda item: item.qualified_name),
        notes=deduped_notes,
    )
