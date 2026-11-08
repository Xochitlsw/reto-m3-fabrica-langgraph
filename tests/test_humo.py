"""Prueba de humo: el entorno tiene las dependencias fijadas y el paquete se importa."""

import sys
from importlib.metadata import version


def test_python_312():
    """El proyecto corre en Python 3.12, no en el python3 del PATH."""
    assert sys.version_info[:2] == (3, 12)


def test_versiones_fijas():
    """Las versiones instaladas son las del diseño (sección 8)."""
    assert version("langgraph") == "1.2.17"
    assert version("langgraph-checkpoint-sqlite") == "3.1.2"
    assert version("pydantic") == "2.14.1"


def test_paquete_importa():
    """El paquete fabrica se importa."""
    import fabrica

    assert fabrica.__version__
