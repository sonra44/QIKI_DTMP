# TASK-0027 — Plugin Architecture v1

## Scope
- Added plugin manager and plugin contracts for radar extension points.
- Migrated existing radar modules to plugin-backed boot path in `RadarPipeline`.
- Added config-driven plugin activation via YAML + ENV strict/non-strict behavior.

## New Files
- `src/qiki/services/q_core_agent/core/plugin_manager.py`
- `src/qiki/services/q_core_agent/core/radar_plugins.py`
- `src/qiki/resources/plugins.yaml`

## Plugin Kinds (v1)
- `sensor_input`: `poll()`, `health()`, `ingest(...)`
- `fusion`: `fuse(tracks_by_source, ...)`
- `render_policy`: `current_policy()`, `load_profile()`, `effective_policy(...)`
- `render_backend`: backend select/render capability path
- `situational_analysis`: situation update/evaluate path

## Config
- `QIKI_PLUGINS_PROFILE` (default: `default`)
- `QIKI_PLUGINS_STRICT=1|0`
- `QIKI_PLUGINS_YAML=/path/to/plugins.yaml` (optional override)

`plugins.yaml` schema:
- `schema_version: 1`
- `profiles.<name>.<kind> = {name, params?, enabled?}`

## Fallback/Strict Rules
- `strict=1`: invalid/missing config is fail-fast.
- `strict=0`: explicit fallback to built-in defaults + `PLUGIN_FALLBACK_USED`.
- No silent fallback.

## EventStore Lifecycle Events
- `PLUGIN_LOADED`
- `PLUGIN_FAILED`
- `PLUGIN_FALLBACK_USED`

Payload fields:
- `name`, `kind`, `version`, `error`, `config_hash`

## Compatibility
- Default profile resolves to existing implementations used in TASK-0022..0026.
- `RadarPipeline` keeps behavior-compatible render/fusion/situation flow, now wired through plugin instances.

## Add New Plugin (3 steps)
1. Implement contract (`SensorInputPlugin` / `FusionPlugin` / etc.) in a module.
2. Register `PluginSpec` in startup registration callback.
3. Reference plugin name in `plugins.yaml` profile and select via `QIKI_PLUGINS_PROFILE`.
