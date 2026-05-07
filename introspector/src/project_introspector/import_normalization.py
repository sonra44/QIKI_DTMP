from __future__ import annotations


def _package_parts(module_path: str) -> list[str]:
    parts = [part for part in module_path.split('.') if part]
    if not parts:
        return []
    return parts[:-1]


def normalize_import(module_path: str, imported: str) -> tuple[str, str, str | None]:
    """Return (normalized_import, import_kind, root) for a raw import string.

    Legacy scanner output stores relative imports as strings like `.models` or `..core`.
    This helper resolves them against the importing module without touching the filesystem.
    """
    raw = (imported or '').strip()
    if not raw:
        return raw, 'absolute', None
    if raw == '__future__' or raw.startswith('__future__.'):
        return raw, 'future', '__future__'
    if not raw.startswith('.'):
        root = raw.split('.', 1)[0] if raw else None
        return raw, 'absolute', root

    level = len(raw) - len(raw.lstrip('.'))
    suffix = raw[level:]
    package = _package_parts(module_path)
    keep = max(len(package) - level + 1, 0)
    base = package[:keep]
    parts = [*base]
    if suffix:
        parts.extend(part for part in suffix.split('.') if part)
    normalized = '.'.join(parts)
    root = parts[0] if parts else None
    return normalized, 'relative', root


def normalized_import_targets(module_path: str, imports: list[str]) -> list[str]:
    values: list[str] = []
    for imported in imports:
        normalized, _kind, _root = normalize_import(module_path, imported)
        if normalized:
            values.append(normalized)
    return sorted(dict.fromkeys(values))
