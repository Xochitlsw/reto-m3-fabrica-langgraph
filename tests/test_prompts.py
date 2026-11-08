"""Paso 6: cada prompt tiene las 6 secciones del diseño (prompt hardening)."""

import pytest

from fabrica.agentes import AGENTES
from fabrica.agentes.base import cargar_prompt

SECCIONES = ("## Rol", "## Reglas", "## Contrato de salida", "## Ejemplo",
             "## Archivos que recibes", "## Errores típicos")


@pytest.mark.parametrize("agente", sorted(AGENTES))
def test_prompt_con_las_seis_secciones(agente):
    """Rol, reglas, contrato, ejemplo, archivos que recibe y errores típicos."""
    texto = cargar_prompt(agente)
    assert [s for s in SECCIONES if s not in texto] == []


@pytest.mark.parametrize("agente", sorted(AGENTES))
def test_prompt_trata_los_datos_como_datos(agente):
    """Cada prompt dice que los delimitadores traen datos y pide solo el JSON del contrato."""
    texto = cargar_prompt(agente)
    assert "dato" in texto and "`<" in texto
    assert "Responde solo con el JSON del contrato" in texto


def test_siete_agentes():
    """Los 7 agentes con modelo del diseño."""
    assert sorted(AGENTES) == sorted(["filtro", "especificador", "planificador", "implementador",
                                      "tester", "reviewer", "documentador"])
