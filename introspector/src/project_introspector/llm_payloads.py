from __future__ import annotations

from collections import Counter
from typing import Any

from .import_normalization import normalized_import_targets
from .module_analysis_policy import ModuleAnalysisPolicy
from .models import ModuleFact, ProjectSchema


PROJECT_LIMITS = {
    'notes': 50,
    'ranked_modules': 60,
    'sampled_modules': 20,
    'edges': 300,
    'top_external_dependencies': 25,
}
MODULE_LIMITS = {
    'imports': 50,
    'functions': 50,
    'classes': 50,
    'class_methods': 100,
    'assignments': 50,
    'runtime_hotspot_candidates': 20,
    'inbound_dependencies': 50,
}


def _module_import_targets(module: ModuleFact) -> list[str]:
    targets = [fact.normalized_import for fact in module.import_facts if fact.normalized_import]
    return sorted(dict.fromkeys(targets or normalized_import_targets(module.module_path, module.imports)))


def _module_fact_extensions(module: ModuleFact) -> dict[str, Any]:
    return {
        'raw_imports': module.imports[:50],
        'import_facts': [fact.model_dump(mode='json') for fact in module.import_facts[:50]],
        'fastapi_routes': [item.model_dump(mode='json') for item in module.fastapi_routes[:50]],
        'env_vars': [item.model_dump(mode='json') for item in module.env_vars[:50]],
        'cli_options': [item.model_dump(mode='json') for item in module.cli_options[:50]],
        'pydantic_models': [item.model_dump(mode='json') for item in module.pydantic_models[:30]],
        'class_attributes': [item.model_dump(mode='json') for item in module.class_attributes[:80]],
    }


def compact_project_schema(schema: ProjectSchema, *, policy: ModuleAnalysisPolicy) -> dict[str, Any]:
    module_index = {module.module_path for module in schema.modules}
    internal_roots = {
        parts[1] if parts[:1] == ['src'] and len(parts) > 1 else parts[0]
        for parts in (module.module_path.split('.') for module in schema.modules)
        if parts
    }
    inbound_imports = Counter(
        edge.target
        for edge in schema.edges
        if edge.kind == 'import' and edge.target in module_index
    )
    runtime_modules = Counter(
        symbol.module_path for symbol in schema.symbols if symbol.runtime_call_count > 0
    )
    runtime_counts = {
        symbol.qualified_name: symbol.runtime_call_count
        for symbol in schema.symbols
        if symbol.runtime_call_count > 0
    }

    def module_score(module: ModuleFact) -> tuple[int, str]:
        parts = module.module_path.split('.')
        interesting_bonus = sum(1 for part in parts if part in policy.INTERESTING_MODULE_TOKENS)
        low_signal_penalty = sum(1 for part in parts if part in policy.LOW_SIGNAL_MODULE_TOKENS)
        doc_bonus = 2 if module.docstring else 0
        symbol_count = len(module.functions) + len(module.classes)
        inbound = inbound_imports[module.module_path]
        runtime = runtime_modules[module.module_path]
        factual_bonus = (
            len(module.fastapi_routes) * 20
            + len(module.cli_options) * 10
            + len(module.env_vars)
            + len(module.pydantic_models) * 5
        )
        score = (
            runtime * 100
            + inbound * 8
            + symbol_count * 2
            + len(_module_import_targets(module))
            + factual_bonus
            + doc_bonus
            + interesting_bonus * 6
            - low_signal_penalty * 40
        )
        return score, module.module_path

    ranked_modules = sorted(schema.modules, key=module_score, reverse=True)
    preferred_modules = [
        module
        for module in ranked_modules
        if not any(part in policy.LOW_SIGNAL_MODULE_TOKENS for part in module.module_path.split('.'))
    ]
    selected_modules = (preferred_modules or ranked_modules)[: PROJECT_LIMITS['ranked_modules']]
    compact_modules = []
    for module in selected_modules:
        imports = _module_import_targets(module)
        compact_modules.append(
            {
                'module_path': module.module_path,
                'inbound_import_count': inbound_imports[module.module_path],
                'runtime_call_count': runtime_modules[module.module_path],
                'imports': imports[:25],
                'functions': [item.qualified_name for item in module.functions[:20]],
                'classes': [item.qualified_name for item in module.classes[:20]],
                'assignments': module.assignments[:20],
                'docstring': (module.docstring or '')[:600] or None,
                'fastapi_routes': [item.model_dump(mode='json') for item in module.fastapi_routes[:20]],
                'env_vars': [item.model_dump(mode='json') for item in module.env_vars[:20]],
                'cli_options': [item.model_dump(mode='json') for item in module.cli_options[:20]],
                'pydantic_models': [item.model_dump(mode='json') for item in module.pydantic_models[:20]],
                'class_attributes': [item.model_dump(mode='json') for item in module.class_attributes[:20]],
            }
        )

    namespace_counts = Counter()
    for module in schema.modules:
        parts = module.module_path.split('.')
        namespace = '.'.join(parts[: min(3, len(parts))])
        namespace_counts[namespace] += 1

    external_dependency_counts = Counter()
    for module in schema.modules:
        for imported in _module_import_targets(module):
            root = imported.split('.')[0]
            if (
                root
                and imported not in module_index
                and root not in internal_roots
                and root not in {'', '__future__'}
            ):
                external_dependency_counts[root] += 1

    likely_entrypoints: list[str] = []
    for module in selected_modules:
        function_names = {item.name for item in module.functions}
        if 'main' in function_names or module.module_path.split('.')[-1] in {'main', 'app', 'cli', 'server'}:
            likely_entrypoints.append(module.module_path)
        if module.fastapi_routes and module.module_path not in likely_entrypoints:
            likely_entrypoints.append(module.module_path)
        if module.cli_options and module.module_path not in likely_entrypoints:
            likely_entrypoints.append(module.module_path)
        if len(likely_entrypoints) >= 20:
            break

    sampled_modules = [
        {
            'module_path': module.module_path,
            'inbound_import_count': inbound_imports[module.module_path],
            'runtime_call_count': runtime_modules[module.module_path],
        }
        for module in ranked_modules[PROJECT_LIMITS['ranked_modules'] : PROJECT_LIMITS['ranked_modules'] + PROJECT_LIMITS['sampled_modules']]
    ]

    truncated_fields = []
    if len(schema.notes) > PROJECT_LIMITS['notes']:
        truncated_fields.append('notes')
    if len(ranked_modules) > PROJECT_LIMITS['ranked_modules']:
        truncated_fields.append('ranked_modules')
    if len(schema.edges) > PROJECT_LIMITS['edges']:
        truncated_fields.append('edges')

    payload_limits = {
        **PROJECT_LIMITS,
        'payload_truncated': bool(truncated_fields),
        'truncated_fields': truncated_fields,
    }
    return {
        'project_name': schema.project_name,
        'module_count': schema.module_count,
        'function_count': schema.function_count,
        'class_count': schema.class_count,
        'runtime_event_count': schema.runtime_event_count,
        'notes': schema.notes[: PROJECT_LIMITS['notes']],
        'likely_entrypoints': likely_entrypoints,
        'namespace_summary': [{'namespace': name, 'module_count': count} for name, count in namespace_counts.most_common(20)],
        'top_external_dependencies': [{'dependency': name, 'import_count': count} for name, count in external_dependency_counts.most_common(PROJECT_LIMITS['top_external_dependencies'])],
        'ranked_modules': compact_modules,
        'sampled_modules': sampled_modules,
        'runtime_call_counts': runtime_counts,
        'edges': [edge.model_dump(mode='json') for edge in schema.edges[: PROJECT_LIMITS['edges']]],
        'payload_limits': payload_limits,
        'payload_truncated': bool(truncated_fields),
        'truncated_fields': truncated_fields,
        'limits': payload_limits,
    }


def compact_module_fact(
    module: ModuleFact,
    *,
    runtime_symbol_counts: dict[str, int] | None = None,
    inbound_dependencies: list[str] | None = None,
) -> dict[str, Any]:
    runtime_symbol_counts = runtime_symbol_counts or {}
    inbound_dependencies = inbound_dependencies or []
    imports = _module_import_targets(module)
    truncated_fields = []
    if len(imports) > MODULE_LIMITS['imports']:
        truncated_fields.append('imports')
    if len(module.functions) > MODULE_LIMITS['functions']:
        truncated_fields.append('functions')
    if len(module.classes) > MODULE_LIMITS['classes']:
        truncated_fields.append('classes')
    if len(inbound_dependencies) > MODULE_LIMITS['inbound_dependencies']:
        truncated_fields.append('inbound_dependencies')
    payload_limits = {
        **MODULE_LIMITS,
        'payload_truncated': bool(truncated_fields),
        'truncated_fields': truncated_fields,
    }
    return {
        'module_path': module.module_path,
        'file_path': module.file_path,
        'imports': imports[: MODULE_LIMITS['imports']],
        'assignments': module.assignments[: MODULE_LIMITS['assignments']],
        'docstring': (module.docstring or '')[:600] or None,
        'runtime_hotspot_candidates': [
            {'qualified_name': name, 'runtime_call_count': count}
            for name, count in sorted(runtime_symbol_counts.items(), key=lambda item: (-item[1], item[0]))[: MODULE_LIMITS['runtime_hotspot_candidates']]
        ],
        'declared_symbols': {
            'module_functions': [item.qualified_name for item in module.functions[: MODULE_LIMITS['functions']]],
            'classes': [item.qualified_name for item in module.classes[: MODULE_LIMITS['classes']]],
            'class_methods': [
                method.qualified_name
                for item in module.classes[: MODULE_LIMITS['classes']]
                for method in item.methods[:50]
            ][: MODULE_LIMITS['class_methods']],
        },
        'functions': [
            {
                'qualified_name': item.qualified_name,
                'parameters': [param.model_dump(mode='json') for param in item.parameters],
                'returns': item.returns,
                'decorators': item.decorators,
                'docstring': (item.docstring or '')[:400] or None,
                'runtime_call_count': runtime_symbol_counts.get(item.qualified_name, 0),
            }
            for item in module.functions[: MODULE_LIMITS['functions']]
        ],
        'classes': [
            {
                'qualified_name': item.qualified_name,
                'bases': item.bases,
                'docstring': (item.docstring or '')[:400] or None,
                'attributes': [attr.model_dump(mode='json') for attr in item.attributes[:50]],
                'methods': [
                    {
                        'qualified_name': method.qualified_name,
                        'runtime_call_count': runtime_symbol_counts.get(method.qualified_name, 0),
                    }
                    for method in item.methods[:50]
                ],
            }
            for item in module.classes[: MODULE_LIMITS['classes']]
        ],
        'inbound_dependencies': inbound_dependencies[: MODULE_LIMITS['inbound_dependencies']],
        **_module_fact_extensions(module),
        'payload_limits': payload_limits,
        'payload_truncated': bool(truncated_fields),
        'truncated_fields': truncated_fields,
        'limits': payload_limits,
    }
