"""Compatibility imports for the project configuration version gate."""

from factoria.application.projects.config_schema import (
    CURRENT_SCHEMA,
    SCHEMA_PATH,
    assert_config_writable,
    schema_version,
)

__all__ = ["CURRENT_SCHEMA", "SCHEMA_PATH", "assert_config_writable", "schema_version"]
