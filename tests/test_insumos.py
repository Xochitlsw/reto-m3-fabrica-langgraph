"""Paso 2: los insumos del dominio existen y traen lo que el diseño pide."""

import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def test_hu05_existe_con_el_texto_del_backlog():
    """HU-05 es el texto literal del backlog de M3B."""
    texto = (RAIZ / "historias" / "HU-05-consultar-antiguedad.md").read_text(encoding="utf-8")
    assert texto.startswith("# HU-05 · Consultar antigüedad")
    assert "antigüedad de cada empleado en años y meses" in texto


def test_reglas_8_a_13_por_numero():
    """reglas_negocio.md trae las reglas 1 a 13, numeradas."""
    texto = (RAIZ / "contexto" / "reglas_negocio.md").read_text(encoding="utf-8")
    numeros = [int(n) for n in re.findall(r"^(\d+)\. ", texto, flags=re.MULTILINE)]
    assert numeros == list(range(1, 14))
    assert "«7 años y 8 meses»" in texto
    assert "La fecha de ingreso no puede ser posterior a la fecha de corte" in texto


def test_operadores_permitidos():
    """La lista de operadores permitidos empieza con xochitl."""
    operadores = json.loads((RAIZ / "config" / "operadores.json").read_text(encoding="utf-8"))
    assert operadores == ["xochitl"]


def test_senuelo_existe_sin_leerlo():
    """El señuelo existe; la prueba no lo lee (solo comprueba que el archivo está)."""
    assert (RAIZ / "secretos_demo.txt").is_file()
