"""Paso 5: revisión estática con AST y lista blanca de imports."""

import pytest

from fabrica import falso
from fabrica.seguridad.revision_codigo import revisar


def _impl(codigo: str, nombre: str = "modulo.py") -> list[str]:
    return revisar([{"nombre": nombre, "contenido": codigo}], "implementacion")


def test_acepta_el_codigo_valido():
    """El código y las pruebas canónicos pasan."""
    assert revisar(falso.IMPLEMENTACION["archivos"], "implementacion") == []
    assert revisar(falso.PRUEBAS["archivos"], "pruebas", ["antiguedad"]) == []


@pytest.mark.parametrize(
    "codigo, esperado",
    [
        ("import os", "import no permitido: os"),
        ("from subprocess import run", "import no permitido: subprocess"),
        ("import os.path", "import no permitido: os.path"),
        ("import socket as s", "import no permitido: socket"),
        ("from . import x", "import relativo"),
        ("from math import *", "import *"),
        ('__import__("os")', "__import__"),
        ('open("x")', "open"),
        ('eval("1")', "eval"),
        ("exec('x=1')", "exec"),
        ("().__class__.__bases__", "atributo interno"),
        ('getattr(x, "__globals__")', "getattr"),
        ("print(__builtins__)", "nombre interno"),
        ('X = "BANDERA-DEMO-12345"', "BANDERA-DEMO"),
        ('RUTA = "../secretos_demo.txt"', "secretos"),
        ('RUTA = ".env"', ".env"),
        ("def f(:\n", "sintaxis inválida"),
    ],
)
def test_rechaza(codigo, esperado):
    """Cada caso peligroso de la sección 5 del diseño se rechaza."""
    problemas = _impl(codigo)
    assert any(esperado in p for p in problemas), problemas


@pytest.mark.parametrize("nombre", ["../x.py", "conftest.py", "a/b.py", "X.py"])
def test_rechaza_nombres(nombre):
    """Rutas, conftest.py y mayúsculas no se aceptan como nombre de archivo."""
    assert any("nombre de archivo" in p for p in _impl("x = 1", nombre))


def test_tamano_y_lineas():
    """Más de 600 líneas o de 20 KB se rechaza."""
    assert any("600" in p for p in _impl("x = 1\n" * 700))


def test_pruebas_pueden_importar_pytest_y_el_modulo_pero_la_implementacion_no():
    """pytest solo en las pruebas; el módulo propio en ambas."""
    codigo = "import pytest\nfrom antiguedad import f\n"
    assert revisar([{"nombre": "test_a.py", "contenido": codigo}], "pruebas", ["antiguedad"]) == []
    problemas = revisar([{"nombre": "a.py", "contenido": codigo}], "implementacion")
    assert any("pytest" in p for p in problemas) and any("antiguedad" in p for p in problemas)


def test_ataque_completo():
    """El código del escenario ataque se rechaza por varios motivos."""
    problemas = _impl(falso.CODIGO_ATAQUE, "antiguedad.py")
    assert any("os" in p for p in problemas) and any("subprocess" in p for p in problemas)


def test_tipo_desconocido():
    """Solo hay dos tipos."""
    with pytest.raises(ValueError):
        revisar([], "otro")
