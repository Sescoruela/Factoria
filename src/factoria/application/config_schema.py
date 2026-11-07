"""Version gate shared by configuration readers/writers; no implicit migration."""

from pathlib import Path

from factoria.config.schema import CURRENT_SCHEMA, SCHEMA_PATH, schema_version


def assert_config_writable(root: Path) -> None:
    schema_version(root)
    from factoria.application.config_recovery import pending_recoveries

    if pending_recoveries(root):
        raise ValueError(
            "Hay una operación de configuración pendiente; revisar project config status y restaurar su copia"
        )
