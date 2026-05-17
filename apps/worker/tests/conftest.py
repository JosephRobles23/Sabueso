"""Pytest config para el worker.

- Marker ``e2e``: corre llamadas reales contra fuentes externas. Off por
  default. Activar con ``pytest -m e2e`` y ``RUN_E2E=1`` o setear los env
  vars correspondientes (``SABUESO_RUN_E2E=1``).
- Fixture ``isolated_registry``: limpia el ``ToolRegistry`` entre tests para
  evitar contaminación cuando un test importa tools y otro espera registry
  vacío.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Hacer importable `src.*` cuando pytest corre desde apps/worker.
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC.parent) not in sys.path:
    sys.path.insert(0, str(SRC.parent))


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "e2e: hits live external sources; requires SABUESO_RUN_E2E=1 and network",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if os.environ.get("SABUESO_RUN_E2E") == "1":
        return
    skip_e2e = pytest.mark.skip(reason="set SABUESO_RUN_E2E=1 to run external-source tests")
    for item in items:
        if "e2e" in item.keywords:
            item.add_marker(skip_e2e)


@pytest.fixture
def isolated_registry():
    """Snapshot/restore del registry para tests que mutan el set de tools."""
    from src.tools.registry import ToolRegistry  # noqa: PLC0415

    snapshot = dict(ToolRegistry._tools)
    yield ToolRegistry
    ToolRegistry._tools.clear()
    ToolRegistry._tools.update(snapshot)
