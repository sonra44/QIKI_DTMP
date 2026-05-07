from __future__ import annotations
import asyncio
import os
from collections.abc import Callable

from .models import ProjectSchema
from .tui_client import IntrospectorTuiClient
from .tui_models import AnalyzerStatus, LivePassSummary, ModuleAnalysisArtifact, ModuleOverviewRow, ProjectScanSummary
from .tui_operations import (
    IntrospectorTuiOperations,
    LivePassResult,
    ModuleViewsRefresh,
    RefreshData,
    ScanProjectResult,
    ReanalyzeResult,
    StatusReload,
    TuiOperationError,
)
from .tui_render import (
    render_action_log,
    render_action_state_block,
    render_analysis_guide,
    render_artifact_block,
    render_compact_detail_block,
    render_live_pass_block,
    render_module_rows,
    render_module_summary,
    render_operator_dashboard,
    render_operator_health_cards,
    render_operator_inspector,
    render_operator_module_table,
    render_project_findings_block,
    render_project_report_block,
    render_project_report_summary_block,
    render_project_scan_block,
    render_replay_status,
    render_storage_block,
)
from .tui_state import build_module_rows, compute_overview_stats, filter_module_rows, filter_report_findings
from .tui_table_model import build_operator_module_table_rows, operator_module_table_headers, operator_module_table_row_values
from .tui_action_history import OperatorActionHistory
from .tui_text import UI_TEXT, tui_text
from .tui_theme import STATUS_THEME_CLASSES, layer_theme_class, operator_state_theme_class, status_theme_class

try:
    from textual import events
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical, VerticalScroll
    from textual.widgets import Button, DataTable, Input, Static, TabbedContent, TabPane, Tree
except ModuleNotFoundError as exc:  # pragma: no cover
    _TEXTUAL_IMPORT_ERROR = exc

    def main() -> None:
        raise SystemExit(
            "Textual is not installed. Install the optional dependency with "
            "`pip install -e .[tui]` or `pip install project-introspector[tui]`."
        )

else:
    _TEXTUAL_IMPORT_ERROR = None
    ACTION_BUTTON_IDS = (
        "#btn-refresh-status",
        "#btn-scan-project",
        "#btn-live-pass",
        "#btn-reanalyze",
    )

    def _mouse_enabled_from_env() -> bool:
        explicit = os.getenv("INTROSPECTOR_TUI_MOUSE")
        if explicit is not None:
            return explicit.strip().lower() in {"1", "true", "yes", "on"}
        return True

    def _compact_mode_from_env() -> bool:
        explicit = os.getenv("INTROSPECTOR_TUI_COMPACT")
        if explicit is None:
            return False
        return explicit.strip().lower() in {"1", "true", "yes", "on"}

    class IntrospectorTuiApp(App[None]):
        AUTO_FOCUS = ""
        ALLOW_SELECT = False
        ENABLE_SELECT_AUTO_SCROLL = False
        ESCAPE_TO_MINIMIZE = False

        CSS = """
        Screen {
            layout: vertical;
        }
        #top-status {
            height: 3;
            padding: 0 1;
        }
        #operator-dashboard {
            height: auto;
        }
        #operator-health-cards {
            height: auto;
        }
        #operator-inspector {
            height: auto;
        }
        #operator-action-log {
            height: auto;
        }
        #overview-top, #overview-middle {
            height: auto;
        }
        #overview-top > Static, #overview-middle > Static {
            width: 1fr;
        }
        #toolbar {
            height: 3;
            padding: 0 1;
        }
        #btn-language {
            width: 18;
            dock: right;
            content-align: center middle;
            text-style: bold;
        }
        #overview-table-scroll, #runtime-table-scroll {
            height: 1fr;
        }
        #overview-data-table {
            height: 1fr;
        }
        #overview-table, #runtime-table {
            padding: 0 1;
        }
        #module-tree {
            width: 42;
            min-width: 32;
            overflow-x: auto;
            overflow-y: auto;
        }
        Tree > .tree--guides-hover {
            color: $text-muted;
            text-style: none;
        }
        Tree > .tree--highlight-line {
            background: transparent;
            color: $text;
            text-style: none;
        }
        Tree > .tree--highlight {
            background: transparent;
            color: $text;
            text-style: none;
        }
        Button:hover {
            background: $surface;
            color: $text;
            text-style: none;
        }
        #compact-main {
            height: 1fr;
            overflow-x: hidden;
            overflow-y: hidden;
        }
        #compact-right {
            width: 1fr;
            overflow-x: hidden;
            overflow-y: auto;
        }
        .panel-title {
            text-style: bold;
            padding: 0 1;
        }
        .panel-body {
            border: solid #666666;
            padding: 0 1;
            margin-bottom: 0;
        }
        #analysis-guide-scroll {
            height: 1fr;
            overflow-y: auto;
            overflow-x: hidden;
        }
        .guide-kicker {
            height: auto;
            padding: 0 1;
            color: #9aa4b2;
        }
        .guide-panel {
            border: tall #444444;
            padding: 0 2;
            margin-bottom: 0;
        }
        .status-ok {
            border: solid #2e7d32;
        }
        .status-warning {
            border: solid #c77c00;
        }
        .status-error {
            border: solid #b00020;
        }
        .status-muted {
            border: solid #666666;
        }
        .status-running {
            border: solid #1565c0;
        }
        .section {
            margin-bottom: 1;
        }
        #explorer-right, #replay-panel {
            width: 1fr;
        }
        .controls {
            height: auto;
            padding: 0 1;
        }
        Button {
            margin-right: 1;
        }
        """

        BINDINGS = [
            Binding("ctrl+q", "quit", "Quit"),
            Binding("r", "refresh_all", "Refresh"),
            Binding("/", "focus_search", "Search"),
            Binding("enter", "open_selected_module", "Open Module"),
            Binding("b", "show_overview", "Back"),
            Binding("s", "cycle_status_filter", "Status Filter"),
            Binding("d", "toggle_degraded", "Degraded Only"),
            Binding("w", "toggle_warnings", "Warnings Only"),
            Binding("l", "reload_status", "Reload Status"),
            Binding("g", "scan_project", "Scan Project"),
            Binding("p", "trigger_live_pass", "Enrich Replay"),
            Binding("a", "trigger_reanalyze", "Enrich Selected"),
            Binding("t", "toggle_language", "RU/EN"),
        ]

        def __init__(self, client: IntrospectorTuiClient | None = None) -> None:
            super().__init__()
            self.client = client or IntrospectorTuiClient.from_env()
            self.operations = IntrospectorTuiOperations(self.client)
            self.initial_module_path = os.getenv("INTROSPECTOR_TUI_INITIAL_MODULE")
            self.initial_tab = os.getenv("INTROSPECTOR_TUI_INITIAL_TAB", "").strip().lower()
            self.language = os.getenv("INTROSPECTOR_TUI_LANG", "en").lower()
            if self.language not in UI_TEXT:
                self.language = "en"
            self.analyzer_status: AnalyzerStatus | None = None
            self.schema: ProjectSchema | None = None
            self.analysis_map: dict[str, ModuleAnalysisArtifact] = {}
            self.project_report: dict[str, object] | None = None
            self.module_rows: list[ModuleOverviewRow] = []
            self.selected_module_path: str | None = None
            self.last_project_scan: ProjectScanSummary | None = None
            self.operator_state = None
            self.overview_status_filter = "all"
            self.runtime_filter = "all"
            self.degraded_only = False
            self.warnings_only = False
            self.last_live_pass: LivePassSummary | None = None
            self.last_error: str | None = None
            self._running_actions: set[str] = set()
            self._action_feedback: dict[str, str] = {}
            self._pending_confirmation: str | None = None
            self._action_history = OperatorActionHistory(max_entries=50)
            self.compact_mode = _compact_mode_from_env()

        def compose(self) -> ComposeResult:
            with Horizontal(id="toolbar"):
                yield Static("", id="app-subtitle")
                yield Button("", id="btn-language")
            yield Static("", id="top-status")
            if self.compact_mode:
                with Horizontal(id="compact-main"):
                    yield Tree("modules", id="module-tree")
                    with VerticalScroll(id="compact-right"):
                        yield Static("", id="operator-dashboard", classes="panel-body")
                        yield Static("", id="operator-health-cards", classes="panel-body")
                        yield Static("", id="operator-inspector", classes="panel-body")
                        yield Static("", id="module-summary", classes="panel-body")
                        yield Static("", id="project-report", classes="panel-body")
                        yield Static("", id="project-findings", classes="panel-body")
                        yield Static("", id="module-detail-body", classes="panel-body")
                        yield Static("", id="module-artifacts", classes="panel-body")
                        yield Static("", id="operator-action-log", classes="panel-body")
                        yield Static("", id="analysis-guide-kicker", classes="guide-kicker")
                        yield Static("", id="analysis-guide", classes="guide-panel")
                        yield Static("", id="compact-actions", classes="panel-body")
                        yield Static("", id="replay-actions", classes="panel-body")
                        yield Static("", id="replay-status", classes="panel-body")
                        yield Static("", id="replay-storage", classes="panel-body")
                        yield Static("", id="replay-last-pass", classes="panel-body")
                return
            with TabbedContent(id="main-tabs"):
                with TabPane(self._text("overview_tab"), id="overview-pane"):
                    with Horizontal(id="overview-top"):
                        yield Static("", id="operator-dashboard", classes="panel-body")
                        yield Static("", id="operator-health-cards", classes="panel-body")
                    with Horizontal(id="overview-middle"):
                        yield Static("", id="operator-inspector", classes="panel-body")
                        yield Static("", id="project-report", classes="panel-body")
                    yield Input(placeholder=self._text("overview_search"), id="overview-search")
                    yield Static("", classes="controls", id="overview-controls")
                    yield Static("", id="project-findings", classes="panel-body")
                    with VerticalScroll(id="overview-table-scroll"):
                        yield DataTable(id="overview-data-table", classes="panel-body")
                        yield Static("", id="overview-table", classes="panel-body")
                    yield Static("", id="operator-action-log", classes="panel-body")
                with TabPane(self._text("explorer_tab"), id="explorer-pane"):
                    with Horizontal():
                        yield Tree("modules", id="module-tree")
                        with VerticalScroll(id="explorer-right"):
                            yield Static(self._text("module_details"), classes="panel-title", id="module-details-title")
                            yield Static("", id="module-summary", classes="panel-body")
                            yield Static("", id="module-detail-body", classes="panel-body")
                            yield Static("", id="module-artifacts", classes="panel-body")
                with TabPane(self._text("runtime_tab"), id="runtime-pane"):
                    yield Input(placeholder=self._text("runtime_search"), id="runtime-search")
                    yield Static("", classes="controls", id="runtime-controls")
                    with VerticalScroll(id="runtime-table-scroll"):
                        yield Static("", id="runtime-table", classes="panel-body")
                with TabPane(self._text("replay_tab"), id="replay-pane"):
                    with Vertical(id="replay-panel"):
                        with Horizontal(classes="controls"):
                            yield Button(self._text("btn_refresh_status"), id="btn-refresh-status")
                            yield Button(self._text("btn_scan_project"), id="btn-scan-project")
                            yield Button(self._text("btn_live_pass"), id="btn-live-pass")
                            yield Button(self._text("btn_reanalyze"), id="btn-reanalyze")
                        yield Static("", id="replay-project-report", classes="panel-body")
                        yield Static("", id="replay-project-findings", classes="panel-body")
                        yield Static("", id="replay-actions", classes="panel-body")
                        yield Static("", id="replay-status", classes="panel-body")
                        yield Static("", id="replay-storage", classes="panel-body")
                        yield Static("", id="replay-last-pass", classes="panel-body")
                with TabPane(self._text("analysis_guide_tab"), id="analysis-guide-pane"):
                    yield Static("", id="analysis-guide-kicker", classes="guide-kicker")
                    with VerticalScroll(id="analysis-guide-scroll"):
                        yield Static("", id="analysis-guide", classes="guide-panel")

        async def on_mount(self) -> None:
            self._refresh_language_text()
            await self.action_refresh_all()
            self._apply_initial_tab_selection()
            self._apply_initial_module_selection()
            if self.compact_mode:
                self.query_one("#module-tree", Tree).focus()

        async def action_refresh_all(self) -> None:
            result = await self._run_sync_action(
                "refresh-all",
                self._text("refreshing_all"),
                lambda: self.operations.load_all_data(selected_module_path=self.selected_module_path),
                label=self._text("btn_refresh_views"),
            )
            if isinstance(result, RefreshData):
                self._apply_refresh_data(result)

        async def action_reload_status(self) -> None:
            result = await self._run_sync_action(
                "reload-status",
                self._text("reloading_status"),
                self.operations.reload_status,
                label=self._text("btn_refresh_status"),
            )
            if isinstance(result, StatusReload):
                self.analyzer_status = result.analyzer_status
                self.project_report = result.project_report
                self.last_project_scan = result.last_project_scan
                self.last_live_pass = result.last_live_pass
                self.operator_state = result.operator_state or self.operator_state
                self.last_error = None
                self._refresh_action_buttons()
                self._refresh_status_panels()

        async def action_scan_project(self) -> None:
            if not self._confirm_action("scan-project"):
                return
            result = await self._run_sync_action(
                "scan-project",
                self._text("running_project_scan"),
                self.operations.run_project_scan,
                label=self._text("btn_scan_project"),
            )
            if isinstance(result, ScanProjectResult):
                self.last_project_scan = result.last_project_scan
                self.query_one("#top-status", Static).update(result.message)
                await self.action_refresh_all()

        async def action_trigger_live_pass(self) -> None:
            if not self._provider_actions_available():
                message = self._text("provider_action_required")
                self._set_action_feedback(
                    "live-pass",
                    self._text("action_failed", message=message),
                )
                self._action_history.record("live-pass", self._text("btn_live_pass"), "failed", message)
                self.query_one("#top-status", Static).update(message)
                self._refresh_replay_panels()
                return
            if not self._confirm_action("live-pass"):
                return
            result = await self._run_sync_action(
                "live-pass",
                self._text("running_live_pass"),
                self.operations.run_live_pass,
                label=self._text("btn_live_pass"),
            )
            if isinstance(result, LivePassResult):
                self.last_live_pass = result.last_live_pass
                self.query_one("#top-status", Static).update(result.message)
                if self.schema is None:
                    await self.action_refresh_all()
                    return
                module_views = await self._run_sync_action(
                    "refresh-module-views",
                    self._text("refreshing_all"),
                    lambda: self.operations.refresh_module_views(
                        schema=self.schema,
                        storage_layout=self.analyzer_status.storage_layout if self.analyzer_status else None,
                        selected_module_path=self.selected_module_path,
                    ),
                    label=self._text("btn_refresh_views"),
                )
                if isinstance(module_views, ModuleViewsRefresh):
                    self._apply_module_views_refresh(module_views)
                else:
                    await self.action_refresh_all()

        async def action_trigger_reanalyze(self) -> None:
            module_path = self.selected_module_path
            if not module_path:
                message = self._text("select_module")
                self._action_history.record("reanalyze", self._text("btn_reanalyze"), "failed", message)
                self.query_one("#top-status", Static).update(message)
                self._refresh_replay_panels()
                return
            if not self._provider_actions_available():
                message = self._text("provider_action_required")
                self._set_action_feedback(
                    "reanalyze",
                    self._text("action_failed", message=message),
                )
                self._action_history.record("reanalyze", self._text("btn_reanalyze"), "failed", message)
                self.query_one("#top-status", Static).update(message)
                self._refresh_replay_panels()
                return
            if not self._confirm_action("reanalyze"):
                return
            result = await self._run_sync_action(
                "reanalyze",
                self._text("reanalyzing", module_path=module_path),
                lambda: self.operations.reanalyze_module(
                    module_path,
                    storage_layout=self.analyzer_status.storage_layout if self.analyzer_status else None,
                ),
                label=self._text("btn_reanalyze"),
            )
            if isinstance(result, ReanalyzeResult):
                self.analysis_map[result.module_path] = result.artifact
                if self.schema is not None:
                    self.module_rows = build_module_rows(self.schema, self.analysis_map)
                self._refresh_views()

        async def _run_sync_action(
            self,
            action_key: str,
            status_message: str,
            operation: Callable[[], object],
            *,
            label: str,
        ) -> object | None:
            if action_key in self._running_actions:
                message = self._text("action_in_progress", label=label)
                self._set_action_feedback(
                    action_key,
                    self._text("action_running"),
                )
                self._action_history.record(action_key, label, "skipped", message)
                self.query_one("#top-status", Static).update(message)
                self._refresh_replay_panels()
                return None
            self._running_actions.add(action_key)
            self._pending_confirmation = None
            self._set_action_feedback(action_key, self._text("action_running"))
            self._action_history.start(action_key, label, message=status_message)
            self._refresh_action_buttons()
            self._refresh_replay_panels()
            self.query_one("#top-status", Static).update(status_message)
            try:
                result = await asyncio.to_thread(operation)
            except TuiOperationError as exc:
                self.last_error = exc.detail or exc.message
                message = exc.detail or exc.message
                self._set_action_feedback(
                    action_key,
                    self._text("action_failed", message=message),
                )
                self._action_history.finish(action_key, state="failed", message=message)
                self._render_error_state()
                return None
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
                self._set_action_feedback(
                    action_key,
                    self._text("action_failed", message=self.last_error),
                )
                self._action_history.finish(action_key, state="failed", message=self.last_error)
                self._render_error_state()
                return None
            finally:
                self._running_actions.discard(action_key)
                self._refresh_action_buttons()
                self._refresh_replay_panels()
            self.last_error = None
            self._set_action_feedback(action_key, self._text("action_done"))
            self._action_history.finish(action_key, state="done", message=self._text("action_done"))
            self._refresh_replay_panels()
            return result

        def _apply_refresh_data(self, result: RefreshData) -> None:
            self.analyzer_status = result.analyzer_status
            self.schema = result.schema
            self.analysis_map = result.analysis_map
            self.project_report = result.project_report
            self.module_rows = result.module_rows
            self.last_project_scan = result.last_project_scan
            self.last_live_pass = result.last_live_pass
            self.selected_module_path = result.selected_module_path
            self.operator_state = result.operator_state
            self.last_error = None
            self._refresh_action_buttons()
            self._refresh_views()

        def _apply_module_views_refresh(self, result: ModuleViewsRefresh) -> None:
            self.analysis_map = result.analysis_map
            self.module_rows = result.module_rows
            self.last_live_pass = result.last_live_pass
            self.selected_module_path = result.selected_module_path
            self.operator_state = result.operator_state or self.operator_state
            self.last_error = None
            self._refresh_views()

        def _refresh_action_buttons(self) -> None:
            if self.compact_mode:
                return
            disabled = bool(self._running_actions)
            for button_id in ACTION_BUTTON_IDS:
                button = self.query_one(button_id, Button)
                button.label = self._action_button_label(button_id)
                if button_id in {"#btn-live-pass", "#btn-reanalyze"} and not self._provider_actions_available():
                    button.disabled = True
                else:
                    button.disabled = disabled
            self._refresh_tooltips()

        def _action_button_label(self, button_id: str) -> str:
            label_keys = {
                "#btn-refresh-status": "btn_refresh_status",
                "#btn-scan-project": "btn_scan_project",
                "#btn-live-pass": "btn_live_pass",
                "#btn-reanalyze": "btn_reanalyze",
            }
            action_keys = {
                "#btn-scan-project": "scan-project",
                "#btn-live-pass": "live-pass",
                "#btn-reanalyze": "reanalyze",
            }
            label = self._text(label_keys[button_id])
            if self._pending_confirmation == action_keys.get(button_id):
                return self._text("btn_confirm_action", action=label)
            return label

        def _confirm_action(self, action_key: str) -> bool:
            if os.getenv("INTROSPECTOR_TUI_CONFIRM_ACTIONS", "1").strip().lower() in {"0", "false", "no", "off"}:
                return True
            if self._pending_confirmation == action_key:
                self._pending_confirmation = None
                self._set_action_feedback(action_key, self._text("action_confirmed"))
                self._refresh_action_buttons()
                self._refresh_replay_panels()
                return True
            self._pending_confirmation = action_key
            message_key = {
                "scan-project": "confirm_scan_project",
                "live-pass": "confirm_live_pass",
                "reanalyze": "confirm_reanalyze",
            }[action_key]
            message = self._text(
                message_key,
                module_path=self.selected_module_path or self._text("unknown"),
            )
            self._set_action_feedback(action_key, self._text("action_confirmation_required", message=message))
            self._action_history.record(action_key, self._action_label(action_key), "pending-confirmation", message)
            self.query_one("#top-status", Static).update(message)
            self._refresh_action_buttons()
            self._refresh_replay_panels()
            return False

        def _action_label(self, action_key: str) -> str:
            label_keys = {
                "scan-project": "btn_scan_project",
                "live-pass": "btn_live_pass",
                "reanalyze": "btn_reanalyze",
                "reload-status": "btn_refresh_status",
                "refresh-all": "btn_refresh_views",
            }
            return self._text(label_keys.get(action_key, "unknown"))

        async def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "btn-language":
                await self.action_toggle_language()
                return
            mapping = {
                "btn-refresh-status": self.action_reload_status,
                "btn-scan-project": self.action_scan_project,
                "btn-live-pass": self.action_trigger_live_pass,
                "btn-reanalyze": self.action_trigger_reanalyze,
            }
            action = mapping.get(event.button.id)
            if action is not None:
                await action()

        def on_key(self, event: events.Key) -> None:
            if event.key == "escape" and self._pending_confirmation:
                action_key = self._pending_confirmation
                self._pending_confirmation = None
                self._set_action_feedback(action_key, self._text("action_confirmation_cancelled"))
                self.query_one("#top-status", Static).update(self._text("confirmation_cancelled"))
                self._refresh_action_buttons()
                self._refresh_replay_panels()
                event.stop()
                event.prevent_default()
                return
            if event.key in {"tab", "shift+tab"}:
                event.stop()
                event.prevent_default()
                return

        def _refresh_views(self) -> None:
            self._refresh_status_panels()
            self._populate_module_tree()
            self._refresh_operator_visual_panels()
            self.query_one("#project-report", Static).update(
                render_project_report_summary_block(self._text, self.project_report)
            )
            self._refresh_project_findings()
            if not self.compact_mode:
                self.query_one("#replay-project-report", Static).update(
                    render_project_report_block(self._text, self.project_report)
                )
                self.query_one("#replay-project-findings", Static).update(
                    self._render_project_findings(search="")
                )
            self._refresh_overview_table()
            self._refresh_runtime_table()
            self._refresh_module_detail()
            self.query_one("#analysis-guide", Static).update(render_analysis_guide(self._text))

        def _refresh_language_text(self) -> None:
            self.title = "Introspector TUI"
            self.sub_title = self._text("app_subtitle")
            self.query_one("#app-subtitle", Static).update(self._text("app_subtitle"))
            self.query_one("#btn-language", Button).label = self._text("lang_button")
            self.query_one("#analysis-guide-kicker", Static).update(self._text("analysis_guide_kicker"))
            if not self.compact_mode:
                self.query_one("#overview-pane", TabPane).label = self._text("overview_tab")
                self.query_one("#explorer-pane", TabPane).label = self._text("explorer_tab")
                self.query_one("#runtime-pane", TabPane).label = self._text("runtime_tab")
                self.query_one("#replay-pane", TabPane).label = self._text("replay_tab")
                self.query_one("#analysis-guide-pane", TabPane).label = self._text("analysis_guide_tab")
                self.query_one("#overview-search", Input).placeholder = self._text("overview_search")
                self.query_one("#runtime-search", Input).placeholder = self._text("runtime_search")
            if not self.compact_mode:
                self.query_one("#module-details-title", Static).update(self._text("module_details"))
            if not self.compact_mode:
                self.query_one("#btn-refresh-status", Button).label = self._text("btn_refresh_status")
                self.query_one("#btn-scan-project", Button).label = self._text("btn_scan_project")
                self.query_one("#btn-live-pass", Button).label = self._text("btn_live_pass")
                self.query_one("#btn-reanalyze", Button).label = self._text("btn_reanalyze")
            self._refresh_tooltips()

        def _text(self, key: str, **kwargs: object) -> str:
            return tui_text(self.language, key, **kwargs)

        def _apply_initial_module_selection(self) -> None:
            if not self.initial_module_path or self.schema is None:
                return
            if not any(module.module_path == self.initial_module_path for module in self.schema.modules):
                return
            self.selected_module_path = self.initial_module_path
            if not self.compact_mode:
                self.query_one("#main-tabs", TabbedContent).active = "explorer-pane"
            self._refresh_module_detail()

        def _apply_initial_tab_selection(self) -> None:
            if self.compact_mode or not self.initial_tab:
                return
            tab_ids = {
                "overview": "overview-pane",
                "explorer": "explorer-pane",
                "module": "explorer-pane",
                "runtime": "runtime-pane",
                "signal": "runtime-pane",
                "scan": "replay-pane",
                "replay": "replay-pane",
                "enrichment": "replay-pane",
                "guide": "analysis-guide-pane",
                "analysis": "analysis-guide-pane",
                "analysis-guide": "analysis-guide-pane",
            }
            tab_id = tab_ids.get(self.initial_tab)
            if tab_id is not None:
                self.query_one("#main-tabs", TabbedContent).active = tab_id

        def _render_error_state(self) -> None:
            message = self.last_error or self._text("unknown_error")
            error_text = self._text("analyzer_error", message=message)
            self.query_one("#top-status", Static).update(error_text)
            self.query_one("#operator-dashboard", Static).update(render_operator_dashboard(self._text, self.operator_state))
            self.query_one("#operator-health-cards", Static).update(render_operator_health_cards(self._text, self.operator_state))
            self.query_one("#operator-inspector", Static).update(render_operator_inspector(self._text, self.operator_state, self.selected_module_path))
            self.query_one("#operator-action-log", Static).update(render_action_log(
                self._text,
                self._action_feedback,
                running_actions=self._running_actions,
                action_history=self._action_history.entries,
            ))
            self.query_one("#replay-status", Static).update(error_text)
            self.query_one("#replay-storage", Static).update(self._text("storage_unavailable"))
            self.query_one("#replay-last-pass", Static).update(self._text("live_pass_unavailable"))
            self.query_one("#replay-actions", Static).update(
                render_action_state_block(self._text, self._action_feedback)
            )
            self.query_one("#analysis-guide", Static).update(render_analysis_guide(self._text))
            self.query_one("#operator-action-log", Static).update(
                render_action_log(
                    self._text,
                    self._action_feedback,
                    running_actions=self._running_actions,
                    action_history=self._action_history.entries,
                )
            )
            self._apply_operator_theme_classes()

        def _refresh_status_panels(self) -> None:
            if self.analyzer_status is None or self.schema is None:
                return
            stats = compute_overview_stats(self.schema.project_name, self.module_rows)
            summary = self._text(
                "summary_line",
                project_name=stats.project_name,
                scan_state=self._text("summary_scan_available"),
                enrichment_state=self._text("summary_enrichment_available")
                if self.analyzer_status.configured
                else self._text("summary_enrichment_waiting_provider"),
                schema_ready=self._text("bool_true") if self.last_project_scan and self.last_project_scan.schema_ready else self._text("bool_false"),
                runtime_merged=self._text("bool_true") if self.last_project_scan and self.last_project_scan.runtime_merged else self._text("bool_false"),
                module_count=stats.module_count,
                runtime_count=stats.runtime_evidence_count,
                degraded_count=stats.degraded_count,
                warning_heavy_count=stats.warning_heavy_count,
                enrichment_pending=sum(1 for row in self.module_rows if row.enrichment_state == "pending"),
                enrichment_done=sum(1 for row in self.module_rows if row.enrichment_state == "done"),
                enrichment_degraded=sum(1 for row in self.module_rows if row.enrichment_state == "degraded"),
            )
            self.query_one("#top-status", Static).update(summary)
            self.query_one("#operator-dashboard", Static).update(
                render_operator_dashboard(self._text, self.operator_state)
            )
            self.query_one("#operator-health-cards", Static).update(
                render_operator_health_cards(self._text, self.operator_state)
            )
            self.query_one("#operator-inspector", Static).update(
                render_operator_inspector(self._text, self.operator_state, self.selected_module_path)
            )
            self.query_one("#project-report", Static).update(
                render_project_report_summary_block(self._text, self.project_report)
            )
            self._refresh_project_findings()
            if not self.compact_mode:
                self.query_one("#overview-controls", Static).update(
                    self._text(
                        "overview_controls",
                        status_filter={
                            "all": self._text("overview_filter_all"),
                            "needs-attention": self._text("overview_filter_needs-attention"),
                            "missing-enrichment": self._text("overview_filter_missing-enrichment"),
                            "has-findings": self._text("overview_filter_has-findings"),
                            "routes": self._text("overview_filter_routes"),
                            "env-config": self._text("overview_filter_env-config"),
                        }.get(self.overview_status_filter, self.overview_status_filter),
                        degraded_only=self.degraded_only,
                        warnings_only=self.warnings_only,
                    )
                )
                self.query_one("#runtime-controls", Static).update(
                    self._text("runtime_controls", runtime_filter=self.runtime_filter)
                )
            self._refresh_replay_panels()

        def _populate_module_tree(self) -> None:
            if self.schema is None:
                return
            tree = self.query_one("#module-tree", Tree)
            tree.clear()
            tree.show_root = not self.compact_mode
            root = tree.root
            root.label = self.schema.project_name
            packages: dict[tuple[str, ...], object] = {(): root}
            for module in sorted(self.schema.modules, key=lambda item: item.module_path):
                parts = module.module_path.split(".")
                for depth in range(1, len(parts)):
                    key = tuple(parts[:depth])
                    parent_key = tuple(parts[: depth - 1])
                    if key not in packages:
                        packages[key] = packages[parent_key].add(parts[depth - 1])
                parent = packages[tuple(parts[:-1])]
                leaf = parent.add(parts[-1], data=module.module_path)
                if module.module_path == self.selected_module_path:
                    leaf.expand()
            root.expand()

        def _refresh_operator_visual_panels(self) -> None:
            self.query_one("#operator-dashboard", Static).update(
                render_operator_dashboard(self._text, self.operator_state)
            )
            self.query_one("#operator-health-cards", Static).update(
                render_operator_health_cards(self._text, self.operator_state)
            )
            self.query_one("#operator-inspector", Static).update(
                render_operator_inspector(self._text, self.operator_state, self.selected_module_path)
            )
            self.query_one("#operator-action-log", Static).update(
                render_action_log(
                    self._text,
                    self._action_feedback,
                    running_actions=self._running_actions,
                    action_history=self._action_history.entries,
                )
            )
            self._apply_operator_theme_classes()

        def _apply_operator_theme_classes(self) -> None:
            self._set_status_class("#top-status", operator_state_theme_class(self.operator_state))
            self._set_status_class("#operator-dashboard", operator_state_theme_class(self.operator_state))
            self._set_status_class("#operator-health-cards", self._overall_layer_theme_class())
            self._set_status_class("#operator-inspector", self._selected_module_theme_class())
            self._set_status_class("#operator-action-log", self._action_log_theme_class())

        def _set_status_class(self, selector: str, class_name: str) -> None:
            widget = self.query_one(selector, Static)
            for status_class in STATUS_THEME_CLASSES:
                widget.remove_class(status_class)
            widget.add_class(class_name)

        def _overall_layer_theme_class(self) -> str:
            if self.operator_state is None:
                return "status-muted"
            layer_classes = [layer_theme_class(self.operator_state, layer.name) for layer in self.operator_state.layers]
            if "status-error" in layer_classes:
                return "status-error"
            if "status-running" in layer_classes:
                return "status-running"
            if "status-warning" in layer_classes:
                return "status-warning"
            if "status-ok" in layer_classes:
                return "status-ok"
            return "status-muted"

        def _selected_module_theme_class(self) -> str:
            if self.operator_state is None or not self.selected_module_path:
                return "status-muted"
            module = next((item for item in self.operator_state.modules if item.module_path == self.selected_module_path), None)
            if module is None:
                return "status-muted"
            if module.degraded:
                return "status-warning"
            if module.enriched:
                return "status-ok"
            return "status-muted"

        def _action_log_theme_class(self) -> str:
            if self._running_actions:
                return "status-running"
            if self.last_error:
                return "status-error"
            last_entry = self._action_history.entries[-1] if self._action_history.entries else None
            if last_entry is not None:
                return status_theme_class(last_entry.state)
            return "status-muted"

        def _refresh_overview_table(self) -> None:
            if self.compact_mode:
                return
            search = self.query_one("#overview-search", Input).value
            filtered = filter_module_rows(
                self.module_rows,
                search=search,
                status_filter=self.overview_status_filter,
                degraded_only=self.degraded_only,
                warnings_only=self.warnings_only,
            )
            if self.operator_state is not None:
                self._refresh_overview_data_table(search=search)
                self.query_one("#overview-table", Static).update(
                    render_operator_module_table(
                        self._text,
                        self.operator_state,
                        selected_module_path=self.selected_module_path,
                        search=search,
                        status_filter=self.overview_status_filter,
                        degraded_only=self.degraded_only,
                    )
                )
            else:
                self._clear_overview_data_table()
                self.query_one("#overview-table", Static).update(render_module_rows(self._text, filtered))

        def _clear_overview_data_table(self) -> None:
            try:
                table = self.query_one("#overview-data-table", DataTable)
            except Exception:
                return
            table.clear(columns=True)

        def _refresh_overview_data_table(self, *, search: str) -> None:
            if self.operator_state is None:
                self._clear_overview_data_table()
                return
            try:
                table = self.query_one("#overview-data-table", DataTable)
            except Exception:
                return
            table.clear(columns=True)
            table.cursor_type = "row"
            table.zebra_stripes = True
            table.add_columns(*operator_module_table_headers(self._text))
            table_rows = build_operator_module_table_rows(
                self.operator_state,
                selected_module_path=self.selected_module_path,
                limit=500,
                search=search,
                status_filter=self.overview_status_filter,
                degraded_only=self.degraded_only,
            )
            for row in table_rows:
                table.add_row(*operator_module_table_row_values(self._text, row), key=row.raw_module_path)

        def _render_project_findings(self, *, search: str) -> str:
            findings = filter_report_findings(
                self.project_report,
                search=search,
                status_filter=self.overview_status_filter,
                degraded_only=self.degraded_only,
                warnings_only=self.warnings_only,
            )
            total_count = 0
            if self.project_report:
                total_count = int(self.project_report.get("module_findings_total") or len(findings))
            return render_project_findings_block(self._text, findings, total_count=total_count)

        def _refresh_project_findings(self) -> None:
            search = ""
            if not self.compact_mode:
                search = self.query_one("#overview-search", Input).value
            self.query_one("#project-findings", Static).update(self._render_project_findings(search=search))
            if not self.compact_mode:
                self.query_one("#replay-project-findings", Static).update(
                    self._render_project_findings(search="")
                )

        def _refresh_runtime_table(self) -> None:
            if self.compact_mode:
                return
            search = self.query_one("#runtime-search", Input).value
            filtered = filter_module_rows(
                self.module_rows,
                search=search,
                runtime_filter=self.runtime_filter,
            )
            self.query_one("#runtime-table", Static).update(
                render_module_rows(self._text, filtered, runtime_mode=True)
            )

        def _refresh_module_detail(self) -> None:
            if self.schema is None or self.selected_module_path is None:
                return
            module = next((item for item in self.schema.modules if item.module_path == self.selected_module_path), None)
            artifact = self.analysis_map.get(self.selected_module_path)
            analysis = artifact.analysis if artifact else None
            enrichment_state = next(
                (row.enrichment_state for row in self.module_rows if row.module_path == self.selected_module_path),
                "pending",
            )
            if "reanalyze" in self._running_actions:
                enrichment_state = "running"
            self.query_one("#module-summary", Static).update(
                render_module_summary(self._text, module, analysis, enrichment_state)
            )
            self.query_one("#module-detail-body", Static).update(
                render_compact_detail_block(self._text, analysis)
            )
            self.query_one("#module-artifacts", Static).update(
                render_artifact_block(self._text, module, artifact, self.last_project_scan)
            )
            self.query_one("#operator-inspector", Static).update(
                render_operator_inspector(self._text, self.operator_state, self.selected_module_path)
            )

        async def on_input_changed(self, event: Input.Changed) -> None:
            if self.compact_mode:
                return
            if event.input.id == "overview-search":
                self._refresh_overview_table()
                self._refresh_project_findings()
            elif event.input.id == "runtime-search":
                self._refresh_runtime_table()

        def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
            if isinstance(event.node.data, str):
                self.selected_module_path = event.node.data
                self._refresh_module_detail()
                self._refresh_overview_table()

        def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
            row_key = getattr(event, "row_key", None)
            module_path = getattr(row_key, "value", None) or str(row_key or "")
            if module_path:
                self.selected_module_path = module_path
                self._refresh_module_detail()
                self._refresh_overview_table()

        async def action_open_selected_module(self) -> None:
            if self.selected_module_path and not self.compact_mode:
                tabs = self.query_one("#main-tabs", TabbedContent)
                tabs.active = "explorer-pane"
                self._refresh_module_detail()

        async def action_show_overview(self) -> None:
            if not self.compact_mode:
                self.query_one("#main-tabs", TabbedContent).active = "overview-pane"

        async def action_toggle_language(self) -> None:
            self.language = "ru" if self.language == "en" else "en"
            self._refresh_language_text()
            self._refresh_views()

        async def action_focus_search(self) -> None:
            if self.compact_mode:
                return
            active = self.query_one("#main-tabs", TabbedContent).active
            if active == "runtime-pane":
                self.query_one("#runtime-search", Input).focus()
            else:
                self.query_one("#overview-search", Input).focus()

        async def action_cycle_status_filter(self) -> None:
            options = [
                "all",
                "active",
                "stale-risk",
                "needs-attention",
                "low-signal",
                "safe-to-ignore",
                "no-analysis",
                "routes",
                "env-config",
                "has-findings",
            ]
            current_index = options.index(self.overview_status_filter)
            self.overview_status_filter = options[(current_index + 1) % len(options)]
            self._refresh_overview_table()
            self._refresh_project_findings()
            self._refresh_status_panels()

        async def action_toggle_degraded(self) -> None:
            self.degraded_only = not self.degraded_only
            self._refresh_overview_table()
            self._refresh_project_findings()
            self._refresh_status_panels()

        async def action_toggle_warnings(self) -> None:
            self.warnings_only = not self.warnings_only
            self._refresh_overview_table()
            self._refresh_project_findings()
            self._refresh_status_panels()

        async def action_cycle_runtime_filter(self) -> None:
            options = ["all", "runtime-only", "static-only", "active-only", "stale-risk-only", "no-runtime-evidence"]
            current_index = options.index(self.runtime_filter)
            self.runtime_filter = options[(current_index + 1) % len(options)]
            self._refresh_runtime_table()
            self._refresh_status_panels()

        def _refresh_replay_panels(self) -> None:
            if self.compact_mode:
                provider_action_suffix = ""
                if not self._provider_actions_available():
                    provider_action_suffix = f" [{self._text('compact_provider_action_unavailable')}]"
                compact_actions = "\n".join(
                    [
                        f"r  {self._text('btn_refresh_status')}",
                        f"g  {self._text('btn_scan_project')}",
                        f"p  {self._text('btn_live_pass')}{provider_action_suffix}",
                        f"a  {self._text('btn_reanalyze')}{provider_action_suffix}",
                    ]
                )
                self.query_one("#compact-actions", Static).update(compact_actions)
            self.query_one("#replay-actions", Static).update(
                render_action_state_block(self._text, self._action_feedback)
            )
            self.query_one("#operator-action-log", Static).update(
                render_action_log(
                    self._text,
                    self._action_feedback,
                    running_actions=self._running_actions,
                    action_history=self._action_history.entries,
                )
            )
            self._apply_operator_theme_classes()
            self.query_one("#replay-status", Static).update(
                render_replay_status(
                    self._text,
                    self.analyzer_status,
                    self.last_project_scan,
                    self.last_live_pass,
                    schema_ready=self.schema is not None,
                    runtime_merged=bool(self.schema and self.schema.runtime_event_count > 0),
                    module_rows=self.module_rows,
                    action_hint=self.last_error or "",
                )
            )
            self.query_one("#replay-storage", Static).update(
                render_storage_block(self._text, self.analyzer_status)
            )
            self.query_one("#replay-last-pass", Static).update(
                "\n\n".join(
                    [
                        render_project_scan_block(self._text, self.last_project_scan),
                        render_live_pass_block(self._text, self.last_live_pass),
                    ]
                )
            )

        def _provider_actions_available(self) -> bool:
            return bool(self.analyzer_status and self.analyzer_status.configured)

        def _set_action_feedback(self, action_key: str, message: str) -> None:
            self._action_feedback[action_key] = message

        def _refresh_tooltips(self) -> None:
            self.query_one("#btn-language", Button).tooltip = self._text("tooltip_lang_button")
            if not self.compact_mode:
                self.query_one("#overview-search", Input).tooltip = self._text("tooltip_overview_search")
                self.query_one("#runtime-search", Input).tooltip = self._text("tooltip_runtime_search")
                self.query_one("#btn-refresh-status", Button).tooltip = self._text("tooltip_refresh_status")
                self.query_one("#btn-scan-project", Button).tooltip = self._text("tooltip_scan_project")
                self.query_one("#btn-live-pass", Button).tooltip = (
                    self._text("tooltip_live_pass")
                    if self._provider_actions_available()
                    else "\n".join(
                        [
                            self._text("tooltip_live_pass"),
                            self._text("tooltip_live_pass_unavailable"),
                        ]
                    )
                )
                self.query_one("#btn-reanalyze", Button).tooltip = (
                    self._text("tooltip_reanalyze")
                    if self._provider_actions_available()
                    else "\n".join(
                        [
                            self._text("tooltip_reanalyze"),
                            self._text("tooltip_reanalyze_unavailable"),
                        ]
                    )
                )
            self.query_one("#module-summary", Static).tooltip = self._text("tooltip_module_summary")
            self.query_one("#module-detail-body", Static).tooltip = self._text("tooltip_module_hints")
            self.query_one("#module-artifacts", Static).tooltip = self._text("tooltip_module_artifacts")
            self.query_one("#operator-dashboard", Static).tooltip = self._text("tooltip_operator_dashboard")
            self.query_one("#operator-health-cards", Static).tooltip = self._text("tooltip_operator_health_cards")
            self.query_one("#operator-inspector", Static).tooltip = self._text("tooltip_operator_inspector")
            self.query_one("#operator-action-log", Static).tooltip = self._text("tooltip_operator_action_log")
            self.query_one("#project-report", Static).tooltip = self._text("tooltip_project_report")
            self.query_one("#project-findings", Static).tooltip = self._text("tooltip_project_findings")
            if not self.compact_mode:
                self.query_one("#replay-project-report", Static).tooltip = self._text("tooltip_project_report")
                self.query_one("#replay-project-findings", Static).tooltip = self._text("tooltip_project_findings")
            self.query_one("#replay-actions", Static).tooltip = self._text("tooltip_replay_actions")
            self.query_one("#replay-status", Static).tooltip = self._text("tooltip_replay_status")
            self.query_one("#replay-storage", Static).tooltip = self._text("tooltip_replay_storage")
            self.query_one("#replay-last-pass", Static).tooltip = self._text("tooltip_replay_last_pass")


    def main() -> None:
        IntrospectorTuiApp().run(mouse=_mouse_enabled_from_env())


if __name__ == "__main__":  # pragma: no cover
    main()
