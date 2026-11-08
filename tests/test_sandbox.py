"""Paso 7: el sandbox corre pytest aislado y no ejecuta código que no pasa la revisión."""

import copy

from fabrica import falso
from fabrica.seguridad import log, sandbox


def _par(codigo: str, prueba: str):
    impl = {"archivos": [{"nombre": "modulo.py", "contenido": codigo}]}
    pru = {"archivos": [{"nombre": "test_modulo.py", "contenido": prueba}]}
    return impl, pru


def test_codigo_bueno_pasa():
    """El antiguedad.py canónico pasa sus 6 pruebas de verdad."""
    r = sandbox.ejecutar(falso.IMPLEMENTACION, falso.PRUEBAS, "e")
    assert r.ok, r.log
    assert (r.aprobadas, r.fallidas, r.errores) == (6, 0, 0)
    assert r.evaluado == "e" and r.aislamiento == "subproceso"


def test_fallo_se_cuenta():
    """El código con error falla CP-02 y el fallo trae el nombre de la prueba."""
    impl = copy.deepcopy(falso.IMPLEMENTACION)
    impl["archivos"][0]["contenido"] = falso.CODIGO_CON_ERROR
    r = sandbox.ejecutar(impl, falso.PRUEBAS)
    assert not r.ok and r.fallidas == 1 and r.aprobadas == 5
    assert "test_cp02" in r.fallos[0]


def test_bucle_infinito_timeout():
    """Un bucle infinito se corta por timeout y se mata el grupo de procesos."""
    impl, pru = _par("def f():\n    while True:\n        pass\n",
                     "from modulo import f\n\ndef test_f():\n    f()\n")
    r = sandbox.ejecutar(impl, pru, timeout=3)
    assert not r.ok and "TIMEOUT" in r.fallos[-1] and r.segundos < 30


def test_sin_pycache_ni_cache(tmp_path):
    """No quedan __pycache__ ni .pytest_cache en la carpeta del sandbox."""
    r = sandbox.ejecutar(falso.IMPLEMENTACION, falso.PRUEBAS, carpeta=tmp_path)
    assert r.ok
    assert not list(tmp_path.rglob("__pycache__")) and not (tmp_path / ".pytest_cache").exists()


def test_codigo_no_permitido_no_ejecuta(tmp_path):
    """Si la revisión estática falla, no se escribe ni se ejecuta nada."""
    impl, pru = _par(falso.CODIGO_ATAQUE, "def test_x():\n    assert True\n")
    r = sandbox.ejecutar(impl, pru, carpeta=tmp_path)
    assert not r.ok and r.problemas_estaticos and r.aprobadas == 0
    assert list(tmp_path.iterdir()) == []


def test_entorno_limpio(tmp_path):
    """El entorno no hereda variables del proceso padre."""
    env = sandbox.entorno_limpio(tmp_path)
    assert set(env) == {"PATH", "HOME", "TMPDIR", "PYTHONDONTWRITEBYTECODE",
                        "PYTEST_DISABLE_PLUGIN_AUTOLOAD", "LANG"}
    assert env["HOME"] == str(tmp_path)


def test_prueba_que_lee_el_entorno_no_ve_secretos(monkeypatch):
    """Una variable secreta del padre no llega al sandbox (la prueba la busca con dict)."""
    monkeypatch.setenv("SECRETO_PADRE", "x")
    impl, pru = _par("import typing\n",
                     "import modulo\n\ndef test_x():\n    assert modulo.typing is not None\n")
    r = sandbox.ejecutar(impl, pru)
    assert r.ok, r.log


def test_error_de_coleccion_no_es_ok():
    """Un import que falla dentro de las pruebas cuenta como error, no como aprobado."""
    impl, pru = _par("X = 1\n", "from modulo import no_existe\n\ndef test_x():\n    pass\n")
    r = sandbox.ejecutar(impl, pru)
    assert not r.ok and r.errores >= 1


def test_nodo_registra_en_el_log():
    """El nodo devuelve la ejecución y deja una línea «sandbox» en el log."""
    estado = {"hilo": "h", "implementacion": {**falso.IMPLEMENTACION, "sha256": "a"},
              "pruebas": {**falso.PRUEBAS, "sha256": "b"}}
    update = sandbox.nodo(estado)
    assert update["ejecucion"]["ok"] and update["ejecucion"]["evaluado"] == "a:b"
    assert log.leer()[0]["evento"] == "sandbox"
