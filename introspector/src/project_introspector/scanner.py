from __future__ import annotations

import ast
import tokenize
from pathlib import Path
from typing import Iterator

from .import_normalization import normalize_import
from .models import (
    AttributeFact,
    ClassFact,
    CliOptionFact,
    CodeLocation,
    EnvVarFact,
    FastAPIRouteFact,
    FunctionFact,
    ImportFact,
    ModuleFact,
    ParameterFact,
    PydanticFieldFact,
    PydanticModelFact,
    ScanError,
    StaticScanEnvelope,
)

IGNORED_DIRS = {".git", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache"}
_FASTAPI_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "api_route"}


def _annotation_to_string(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:
        return None


def _constant_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _constant_bool(node: ast.AST | None) -> bool | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return bool(node.value)
    return None


def _location(file_path: str, module_path: str, node: ast.AST) -> CodeLocation:
    return CodeLocation(
        file_path=file_path,
        module_path=module_path,
        lineno=getattr(node, "lineno", None),
        end_lineno=getattr(node, "end_lineno", None),
    )


class ModuleVisitor(ast.NodeVisitor):
    def __init__(self, module_path: str, file_path: str):
        self.module_path = module_path
        self.file_path = file_path
        self.imports: list[str] = []
        self.import_facts: list[ImportFact] = []
        self.functions: list[FunctionFact] = []
        self.classes: list[ClassFact] = []
        self.assignments: list[str] = []
        self.fastapi_routes: list[FastAPIRouteFact] = []
        self.env_vars: list[EnvVarFact] = []
        self.cli_options: list[CliOptionFact] = []
        self.pydantic_models: list[PydanticModelFact] = []
        self.class_attributes: list[AttributeFact] = []
        self._class_stack: list[ClassFact] = []
        self._function_depth = 0
        self._pydantic_base_names: set[str] = {"BaseModel"}

    def _loc(self, node: ast.AST) -> CodeLocation:
        return _location(self.file_path, self.module_path, node)

    def _add_import_fact(
        self,
        node: ast.AST,
        *,
        raw_import: str,
        imported_names: list[str],
        is_from_import: bool,
    ) -> None:
        normalized, import_kind, root = normalize_import(self.module_path, raw_import)
        self.imports.append(raw_import)
        self.import_facts.append(
            ImportFact(
                raw_import=raw_import,
                normalized_import=normalized,
                import_kind=import_kind,  # type: ignore[arg-type]
                root=root,
                imported_names=imported_names,
                is_from_import=is_from_import,
                location=self._loc(node),
            )
        )

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._add_import_fact(
                node,
                raw_import=alias.name,
                imported_names=[alias.asname or alias.name],
                is_from_import=False,
            )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        imported_names = [alias.asname or alias.name for alias in node.names]
        if module == "pydantic":
            for alias in node.names:
                if alias.name == "BaseModel":
                    self._pydantic_base_names.add(alias.asname or alias.name)
        if node.level and not module and imported_names and imported_names != ["*"]:
            for alias in node.names:
                name = alias.asname or alias.name
                raw = f"{'.' * node.level}{alias.name}"
                self._add_import_fact(
                    node,
                    raw_import=raw,
                    imported_names=[name],
                    is_from_import=True,
                )
        else:
            raw = f"{'.' * node.level}{module}" if node.level else module
            if not raw and node.level:
                raw = "." * node.level
            if raw:
                self._add_import_fact(
                    node,
                    raw_import=raw,
                    imported_names=imported_names,
                    is_from_import=True,
                )
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        if not self._class_stack and self._function_depth == 0:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.assignments.append(target.id)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if not self._class_stack and self._function_depth == 0 and isinstance(node.target, ast.Name):
            self.assignments.append(node.target.id)
        self.generic_visit(node)

    def _build_parameters(self, node: ast.arguments) -> list[ParameterFact]:
        positional = [*node.posonlyargs, *node.args]
        defaults_offset = len(positional) - len(node.defaults)
        params: list[ParameterFact] = []
        for idx, arg in enumerate(positional):
            params.append(
                ParameterFact(
                    name=arg.arg,
                    annotation=_annotation_to_string(arg.annotation),
                    has_default=idx >= defaults_offset,
                )
            )
        if node.vararg:
            params.append(
                ParameterFact(
                    name=f"*{node.vararg.arg}",
                    annotation=_annotation_to_string(node.vararg.annotation),
                    has_default=False,
                )
            )
        for kwonly_arg, default in zip(node.kwonlyargs, node.kw_defaults):
            params.append(
                ParameterFact(
                    name=kwonly_arg.arg,
                    annotation=_annotation_to_string(kwonly_arg.annotation),
                    has_default=default is not None,
                )
            )
        if node.kwarg:
            params.append(
                ParameterFact(
                    name=f"**{node.kwarg.arg}",
                    annotation=_annotation_to_string(node.kwarg.annotation),
                    has_default=False,
                )
            )
        return params

    def _build_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> FunctionFact:
        owner = ".".join(item.name for item in self._class_stack)
        qualified_name = (
            f"{self.module_path}.{node.name}"
            if not owner
            else f"{self.module_path}.{owner}.{node.name}"
        )
        return FunctionFact(
            name=node.name,
            qualified_name=qualified_name,
            location=self._loc(node),
            parameters=self._build_parameters(node.args),
            returns=_annotation_to_string(node.returns),
            decorators=[_annotation_to_string(d) or "<decorator>" for d in node.decorator_list],
            docstring=ast.get_docstring(node),
            is_async=isinstance(node, ast.AsyncFunctionDef),
        )

    def _collect_instance_attributes(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        *,
        class_fact: ClassFact,
    ) -> list[AttributeFact]:
        attrs: list[AttributeFact] = []
        seen: set[tuple[str, str | None]] = set()

        def add_attr(target: ast.Attribute, annotation: str | None = None) -> None:
            if not isinstance(target.value, ast.Name) or target.value.id != "self":
                return
            key = (target.attr, annotation)
            if key in seen:
                return
            seen.add(key)
            attrs.append(
                AttributeFact(
                    class_name=class_fact.qualified_name,
                    qualified_name=f"{class_fact.qualified_name}.{target.attr}",
                    attribute_name=target.attr,
                    attribute_kind="instance",
                    defined_in=f"{class_fact.qualified_name}.{node.name}",
                    annotation=annotation,
                    location=self._loc(target),
                )
            )

        for child in ast.walk(node):
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, ast.Attribute):
                        add_attr(target)
            elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Attribute):
                add_attr(child.target, _annotation_to_string(child.annotation))
        return attrs

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        fact = self._build_function(node)
        if self._class_stack:
            current_class = self._class_stack[-1]
            current_class.methods.append(fact)
            attrs = self._collect_instance_attributes(node, class_fact=current_class)
            current_class.attributes.extend(attrs)
            self.class_attributes.extend(attrs)
        else:
            self.functions.append(fact)
        self._collect_fastapi_routes(node, fact)
        self._function_depth += 1
        self.generic_visit(node)
        self._function_depth -= 1

    def _class_attribute_fact(
        self,
        node: ast.AST,
        *,
        class_fact: ClassFact,
        attr_name: str,
        annotation: str | None = None,
    ) -> AttributeFact:
        return AttributeFact(
            class_name=class_fact.qualified_name,
            qualified_name=f"{class_fact.qualified_name}.{attr_name}",
            attribute_name=attr_name,
            attribute_kind="class",
            defined_in=class_fact.qualified_name,
            annotation=annotation,
            location=self._loc(node),
        )

    def _class_attribute_facts(self, node: ast.ClassDef, *, class_fact: ClassFact) -> list[AttributeFact]:
        attrs: list[AttributeFact] = []
        for stmt in node.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        attrs.append(self._class_attribute_fact(stmt, class_fact=class_fact, attr_name=target.id))
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                attrs.append(
                    self._class_attribute_fact(
                        stmt,
                        class_fact=class_fact,
                        attr_name=stmt.target.id,
                        annotation=_annotation_to_string(stmt.annotation),
                    )
                )
        return attrs

    def _pydantic_model_fact(self, node: ast.ClassDef, *, class_fact: ClassFact) -> PydanticModelFact | None:
        bases = [_annotation_to_string(base) or "<base>" for base in node.bases]
        if not any(base in self._pydantic_base_names or base.endswith(".BaseModel") for base in bases):
            return None
        fields: list[PydanticFieldFact] = []
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                fields.append(
                    PydanticFieldFact(
                        name=stmt.target.id,
                        annotation=_annotation_to_string(stmt.annotation),
                        has_default=stmt.value is not None,
                        default=_annotation_to_string(stmt.value),
                    )
                )
            elif isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        fields.append(
                            PydanticFieldFact(
                                name=target.id,
                                annotation=None,
                                has_default=True,
                                default=_annotation_to_string(stmt.value),
                            )
                        )
        return PydanticModelFact(
            name=node.name,
            qualified_name=class_fact.qualified_name,
            bases=bases,
            fields=fields,
            location=self._loc(node),
        )

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        owner = ".".join(item.name for item in self._class_stack)
        qualified_name = f"{self.module_path}.{node.name}" if not owner else f"{self.module_path}.{owner}.{node.name}"
        class_fact = ClassFact(
            name=node.name,
            qualified_name=qualified_name,
            location=self._loc(node),
            bases=[_annotation_to_string(base) or "<base>" for base in node.bases],
            decorators=[_annotation_to_string(d) or "<decorator>" for d in node.decorator_list],
            docstring=ast.get_docstring(node),
        )
        class_attrs = self._class_attribute_facts(node, class_fact=class_fact)
        class_fact.attributes.extend(class_attrs)
        self.class_attributes.extend(class_attrs)
        pydantic_fact = self._pydantic_model_fact(node, class_fact=class_fact)
        if pydantic_fact:
            self.pydantic_models.append(pydantic_fact)
        self.classes.append(class_fact)
        self._class_stack.append(class_fact)
        self.generic_visit(node)
        self._class_stack.pop()

    def _collect_fastapi_routes(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        function_fact: FunctionFact,
    ) -> None:
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            func = decorator.func
            if not isinstance(func, ast.Attribute) or func.attr not in _FASTAPI_METHODS:
                continue
            path = _constant_string(decorator.args[0]) if decorator.args else None
            if not path:
                for kw in decorator.keywords:
                    if kw.arg in {"path", "route"}:
                        path = _constant_string(kw.value)
                        break
            if not path:
                continue
            app_name = _annotation_to_string(func.value)
            self.fastapi_routes.append(
                FastAPIRouteFact(
                    method=func.attr.upper() if func.attr != "api_route" else "API_ROUTE",
                    path=path,
                    qualified_name=function_fact.qualified_name,
                    decorator=_annotation_to_string(decorator) or "<decorator>",
                    app_name=app_name,
                    location=self._loc(decorator),
                )
            )

    def visit_Call(self, node: ast.Call) -> None:
        self._collect_env_var(node)
        self._collect_cli_option(node)
        self.generic_visit(node)

    def _collect_env_var(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Attribute):
            value = func.value
            if isinstance(value, ast.Name) and value.id == "os" and func.attr == "getenv":
                name = _constant_string(node.args[0]) if node.args else None
                if name:
                    self.env_vars.append(
                        EnvVarFact(
                            name=name,
                            access_kind="getenv",
                            default=_constant_string(node.args[1]) if len(node.args) > 1 else None,
                            location=self._loc(node),
                        )
                    )
            elif (
                isinstance(value, ast.Attribute)
                and isinstance(value.value, ast.Name)
                and value.value.id == "os"
                and value.attr == "environ"
                and func.attr in {"get", "setdefault"}
            ):
                name = _constant_string(node.args[0]) if node.args else None
                if name:
                    self.env_vars.append(
                        EnvVarFact(
                            name=name,
                            access_kind=func.attr,  # type: ignore[arg-type]
                            default=_constant_string(node.args[1]) if len(node.args) > 1 else None,
                            location=self._loc(node),
                        )
                    )

    def visit_Subscript(self, node: ast.Subscript) -> None:
        value = node.value
        if (
            isinstance(value, ast.Attribute)
            and isinstance(value.value, ast.Name)
            and value.value.id == "os"
            and value.attr == "environ"
        ):
            name = _constant_string(node.slice)
            if name:
                self.env_vars.append(
                    EnvVarFact(name=name, access_kind="getitem", default=None, location=self._loc(node))
                )
        self.generic_visit(node)

    def _collect_cli_option(self, node: ast.Call) -> None:
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "add_argument":
            return
        option_strings = [value for arg in node.args if (value := _constant_string(arg))]
        if not option_strings:
            return
        kw = {item.arg: item.value for item in node.keywords if item.arg}
        self.cli_options.append(
            CliOptionFact(
                option_strings=option_strings,
                dest=_constant_string(kw.get("dest")),
                default=_annotation_to_string(kw.get("default")) if kw.get("default") is not None else None,
                required=_constant_bool(kw.get("required")),
                action=_constant_string(kw.get("action")),
                help=_constant_string(kw.get("help")),
                location=self._loc(node),
            )
        )


def _module_path(root_path: Path, file_path: Path) -> str:
    rel = file_path.relative_to(root_path).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _iter_python_files(root_path: Path) -> Iterator[Path]:
    for path in sorted(root_path.rglob("*.py")):
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        yield path


def _read_python_source(file_path: Path) -> str:
    with tokenize.open(str(file_path)) as handle:
        return handle.read()


def scan_project(root_path: Path, project_name: str) -> StaticScanEnvelope:
    root_path = root_path.resolve()
    modules: list[ModuleFact] = []
    scan_errors: list[ScanError] = []
    for file_path in _iter_python_files(root_path):
        module_path = _module_path(root_path, file_path)
        try:
            source = _read_python_source(file_path)
            tree = ast.parse(source, filename=str(file_path))
        except Exception as exc:
            scan_errors.append(
                ScanError(
                    file_path=str(file_path),
                    module_path=module_path,
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
            )
            continue

        visitor = ModuleVisitor(module_path=module_path, file_path=str(file_path))
        visitor.visit(tree)
        modules.append(
            ModuleFact(
                module_path=module_path,
                file_path=str(file_path),
                file_hash=ModuleFact.hash_source(source),
                imports=sorted(set(visitor.imports)),
                import_facts=sorted(visitor.import_facts, key=lambda item: (item.normalized_import, item.raw_import)),
                functions=visitor.functions,
                classes=visitor.classes,
                assignments=sorted(set(visitor.assignments)),
                docstring=ast.get_docstring(tree),
                fastapi_routes=visitor.fastapi_routes,
                env_vars=sorted(visitor.env_vars, key=lambda item: (item.name, item.access_kind, item.location.lineno or 0)),
                cli_options=visitor.cli_options,
                pydantic_models=visitor.pydantic_models,
                class_attributes=sorted(visitor.class_attributes, key=lambda item: item.qualified_name),
            )
        )
    modules.sort(key=lambda module: module.module_path)
    return StaticScanEnvelope(
        project_name=project_name,
        root_path=str(root_path),
        modules=modules,
        scan_errors=scan_errors,
    )
