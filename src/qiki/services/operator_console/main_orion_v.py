"""ORION V entrypoint."""

try:
    from qiki.services.operator_console.orion_v.app import OrionVApp
except ModuleNotFoundError:  # pragma: no cover - local /app fallback
    from orion_v.app import OrionVApp


if __name__ == "__main__":
    OrionVApp().run()
