"""Fixtures comunes: ninguna prueba escribe en logs/, salida/ ni evidencia/ reales."""

import pytest


@pytest.fixture(autouse=True)
def rutas_temporales(tmp_path, monkeypatch):
    """Redirige el log, la salida, la evidencia y la base a una carpeta temporal por prueba."""
    monkeypatch.setenv("FABRICA_LOG", str(tmp_path / "logs" / "seguridad.jsonl"))
    monkeypatch.setenv("FABRICA_SALIDA", str(tmp_path / "salida"))
    monkeypatch.setenv("FABRICA_EVIDENCIA", str(tmp_path / "evidencia"))
    monkeypatch.setenv("FABRICA_DB", str(tmp_path / "datos" / "checkpoints.sqlite"))
    monkeypatch.delenv("DEFENSAS", raising=False)
    return tmp_path
