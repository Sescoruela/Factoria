"""Version gate shared by configuration readers/writers; no implicit migration."""
import json
from pathlib import Path

SCHEMA_PATH = '.factoria/schema.json'
CURRENT_SCHEMA = 1


def schema_version(root: Path) -> int:
    from factoria.application.project_integration import project_path
    path = project_path(root, SCHEMA_PATH)
    if not path.exists():
        return 0
    if not path.is_file() or path.stat().st_size > 4096:
        raise ValueError('Marcador de esquema no válido')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result: raise ValueError('Esquema con claves duplicadas')
            result[key] = value
        return result
    data = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique)
    if (not isinstance(data, dict) or set(data) != {'schema_version'}
            or type(data['schema_version']) is not int or data['schema_version'] != CURRENT_SCHEMA):
        raise ValueError('Esquema incompatible; no se lee ni modifica con esta versión de Factoria')
    return data['schema_version']


def assert_config_writable(root: Path) -> None:
    schema_version(root)
    from factoria.application.config_recovery import pending_recoveries
    if pending_recoveries(root):
        raise ValueError('Hay una operación de configuración pendiente; revisar project config status y restaurar su copia')
