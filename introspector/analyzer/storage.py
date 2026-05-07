from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from project_introspector.models import RuntimeEvent, StaticScanEnvelope

logger = logging.getLogger(__name__)
_SAFE_PROJECT_CHARS = re.compile(r"[^A-Za-z0-9_.-]+")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class StorageHealth:
    backend: str
    db_path: str
    single_writer: bool
    retention_days: int
    max_runtime_events_per_project: int


class AnalyzerStorage:
    def __init__(
        self,
        data_dir: Path,
        *,
        retention_days: int = 30,
        max_runtime_events_per_project: int = 5000,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.retention_days = retention_days
        self.max_runtime_events_per_project = max_runtime_events_per_project
        self.lock = threading.RLock()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / 'analyzer.sqlite3'
        self.static_dir = self.data_dir / 'static'
        self.runtime_dir = self.data_dir / 'runtime'
        self.derived_dir = self.data_dir / 'derived'
        for path in (self.static_dir, self.runtime_dir, self.derived_dir):
            path.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def health(self) -> StorageHealth:
        return StorageHealth(
            backend='sqlite+json-mirror',
            db_path=str(self.db_path.resolve()),
            single_writer=True,
            retention_days=self.retention_days,
            max_runtime_events_per_project=self.max_runtime_events_per_project,
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA foreign_keys=ON')
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS static_snapshots (
                    project_name TEXT PRIMARY KEY,
                    scanned_at TEXT,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    event_json TEXT NOT NULL
                )
                """
            )
            conn.execute('CREATE INDEX IF NOT EXISTS idx_runtime_events_project_id ON runtime_events(project_name, id)')
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS derived_docs (
                    project_name TEXT NOT NULL,
                    doc_key TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (project_name, doc_key)
                )
                """
            )
            conn.commit()

    def safe_project_name(self, project_name: str) -> str:
        normalized = _SAFE_PROJECT_CHARS.sub('_', project_name.strip()).strip('._')
        if not normalized:
            raise ValueError('project_name must contain at least one safe character')
        return normalized

    def _atomic_write_json(self, path: Path, payload: object) -> None:
        tmp_path = path.with_name(f'.{path.name}.{uuid4().hex}.tmp')
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp_path.replace(path)

    def _project_file(self, project_name: str, suffix: str) -> Path:
        safe_name = self.safe_project_name(project_name)
        safe_suffix = _SAFE_PROJECT_CHARS.sub('_', suffix).strip('._') or 'data'
        if safe_suffix == 'static':
            return self.static_dir / f'{safe_name}.json'
        if safe_suffix == 'runtime':
            return self.runtime_dir / f'{safe_name}.json'
        return self.derived_dir / f'{safe_name}.{safe_suffix}.json'

    def write_static(self, payload: StaticScanEnvelope) -> None:
        dumped = payload.model_dump(mode='json')
        with self.lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO static_snapshots(project_name, scanned_at, payload_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(project_name) DO UPDATE SET
                    scanned_at=excluded.scanned_at,
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at
                """,
                (
                    payload.project_name,
                    payload.scanned_at.isoformat(),
                    json.dumps(dumped, ensure_ascii=False),
                    utc_now_iso(),
                ),
            )
            conn.commit()
        self._atomic_write_json(self._project_file(payload.project_name, 'static'), dumped)

    def append_runtime(self, payload: list[RuntimeEvent]) -> None:
        if not payload:
            return
        project_name = payload[0].project_name
        dumped = [event.model_dump(mode='json') for event in payload]
        with self.lock, self._connect() as conn:
            conn.executemany(
                'INSERT INTO runtime_events(project_name, created_at, event_json) VALUES (?, ?, ?)',
                [
                    (
                        project_name,
                        event.timestamp.isoformat(),
                        json.dumps(item, ensure_ascii=False),
                    )
                    for event, item in zip(payload, dumped, strict=True)
                ],
            )
            self._compact_runtime(conn, project_name)
            rows = conn.execute(
                'SELECT event_json FROM runtime_events WHERE project_name=? ORDER BY id',
                (project_name,),
            ).fetchall()
            conn.commit()
        self._atomic_write_json(self._project_file(project_name, 'runtime'), [json.loads(row['event_json']) for row in rows])

    def _compact_runtime(self, conn: sqlite3.Connection, project_name: str) -> None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.retention_days)).isoformat()
        conn.execute(
            'DELETE FROM runtime_events WHERE project_name=? AND created_at < ?',
            (project_name, cutoff),
        )
        extra = conn.execute(
            'SELECT COUNT(*) AS count FROM runtime_events WHERE project_name=?',
            (project_name,),
        ).fetchone()['count'] - self.max_runtime_events_per_project
        if extra > 0:
            conn.execute(
                """
                DELETE FROM runtime_events
                WHERE id IN (
                    SELECT id FROM runtime_events
                    WHERE project_name=?
                    ORDER BY id ASC
                    LIMIT ?
                )
                """,
                (project_name, extra),
            )

    def load_static(self, project_name: str) -> StaticScanEnvelope | None:
        with self.lock, self._connect() as conn:
            row = conn.execute(
                'SELECT payload_json FROM static_snapshots WHERE project_name=?',
                (project_name,),
            ).fetchone()
        if row is None:
            path = self._project_file(project_name, 'static')
            if not path.exists():
                return None
            return StaticScanEnvelope.model_validate_json(path.read_text(encoding='utf-8'))
        return StaticScanEnvelope.model_validate_json(row['payload_json'])

    def load_runtime(self, project_name: str, *, warnings: list[str] | None = None) -> list[RuntimeEvent]:
        with self.lock, self._connect() as conn:
            rows = conn.execute(
                'SELECT event_json FROM runtime_events WHERE project_name=? ORDER BY id',
                (project_name,),
            ).fetchall()
        events: list[RuntimeEvent] = []
        for row in rows:
            try:
                events.append(RuntimeEvent.model_validate_json(row['event_json']))
            except Exception as exc:
                if warnings is not None:
                    warnings.append(f'Skipped invalid runtime event from sqlite: {type(exc).__name__}: {exc}')
        return events

    def write_derived(self, project_name: str, doc_key: str, payload: dict[str, object]) -> None:
        with self.lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO derived_docs(project_name, doc_key, payload_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(project_name, doc_key) DO UPDATE SET
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at
                """,
                (project_name, doc_key, json.dumps(payload, ensure_ascii=False), utc_now_iso()),
            )
            conn.commit()
        self._atomic_write_json(self._project_file(project_name, doc_key), payload)


    def load_derived(self, project_name: str, doc_key: str) -> dict[str, object] | None:
        with self.lock, self._connect() as conn:
            row = conn.execute(
                'SELECT payload_json FROM derived_docs WHERE project_name=? AND doc_key=?',
                (project_name, doc_key),
            ).fetchone()
        if row is None:
            path = self._project_file(project_name, doc_key)
            if not path.exists():
                return None
            return json.loads(path.read_text(encoding='utf-8'))
        return json.loads(row['payload_json'])

    def list_derived(self, project_name: str, *, prefix: str | None = None) -> list[dict[str, object]]:
        query = 'SELECT doc_key, payload_json, updated_at FROM derived_docs WHERE project_name=?'
        params: list[object] = [project_name]
        if prefix:
            query += ' AND doc_key LIKE ?'
            params.append(f'{prefix}%')
        query += ' ORDER BY doc_key ASC'
        with self.lock, self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        items: list[dict[str, object]] = []
        for row in rows:
            payload = json.loads(row['payload_json'])
            items.append({
                'doc_key': row['doc_key'],
                'updated_at': row['updated_at'],
                'payload': payload,
            })
        return items
