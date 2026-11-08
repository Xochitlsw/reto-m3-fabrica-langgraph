"""Paso 7 y fase 3: el sandbox corre pytest aislado, con rlimit y sandbox-exec, y no ejecuta
código que no pasa la revisión (docs/diseno.md, sección 5)."""

import copy

import pytest

from fabrica import config, falso
from fabrica.seguridad import log, sandbox

SENUELO = str((config.RAIZ / "secretos_demo.txt").resolve())
sin_sandbox_exec = pytest.mark.skipif(
    not sandbox.sandbox_exec_disponible(), reason="sandbox-exec no disponible en esta máquina")


def _par(codigo: str, prueba: str):
    impl = {"archivos": [{"nombre": "modulo.py", "contenido": codigo}]}
    pru = {"archivos": [{"nombre": "test_modulo.py", "contenido": prueba}]}
    return impl, pru


@pytest.fixture
def sin_revision(monkeypatch):
    """Apaga la revisión estática solo dentro de una prueba: deja ver la segunda capa (sandbox)."""
    monkeypatch.setattr(sandbox, "revisar", lambda *a, **k: [])


def test_codigo_bueno_pasa():
    """El antiguedad.py canónico pasa sus 6 pruebas de verdad, incluso bajo sandbox-exec."""
    r = sandbox.ejecutar(falso.IMPLEMENTACION, falso.PRUEBAS, "e")
    assert r.ok, r.log
    assert (r.aprobadas, r.fallidas, r.errores) == (6, 0, 0)
    esperado = "sandbox-exec" if sandbox.sandbox_exec_disponible() else "subproceso"
    assert r.evaluado == "e" and r.aislamiento == esperado


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


# --- Fase 3: rlimit ----------------------------------------------------------------------------
def test_rlimit_fsize_corta_archivo_enorme(sin_revision):
    """Escribir más de 5 MB dispara RLIMIT_FSIZE y la prueba no pasa (segunda capa)."""
    codigo = ("def genera():\n    with open('enorme.bin', 'w') as f:\n"
              "        f.write('x' * 20_000_000)\n")
    impl, pru = _par(codigo, "from modulo import genera\n\ndef test_g():\n    genera()\n")
    r = sandbox.ejecutar(impl, pru, timeout=30)
    assert not r.ok and (r.fallidas or r.errores)


def test_limites_incluye_cpu_fsize_nofile_sin_nproc(monkeypatch):
    """_limites aplica CPU, tamaño y descriptores; nunca RLIMIT_NPROC (cuenta todo el usuario)."""
    import resource
    puestos = []
    monkeypatch.setattr("os.setsid", lambda: None)  # no crear una sesión en el proceso de pytest
    monkeypatch.setattr(resource, "setrlimit", lambda recurso, limites: puestos.append(recurso))
    sandbox._limites()
    assert set(puestos) == {resource.RLIMIT_CPU, resource.RLIMIT_FSIZE, resource.RLIMIT_NOFILE}
    assert resource.RLIMIT_NPROC not in puestos
    assert (sandbox.CPU_SEGUNDOS, sandbox.FSIZE_BYTES, sandbox.NOFILE) == (30, 5 * 1024 * 1024, 128)


# --- Fase 3: sandbox-exec (se saltan si no existe) ---------------------------------------------
@sin_sandbox_exec
def test_sandbox_exec_niega_la_red(sin_revision):
    """Bajo el perfil, abrir un socket a la red falla."""
    impl, pru = _par(
        "import socket\n\ndef conecta():\n    socket.socket().connect(('1.1.1.1', 80))\n",
        "from modulo import conecta\n\ndef test_c():\n    conecta()\n",
    )
    assert not sandbox.ejecutar(impl, pru, timeout=30).ok


@sin_sandbox_exec
def test_sandbox_exec_niega_leer_el_senuelo(sin_revision):
    """Bajo el perfil, leer secretos_demo.txt falla y la bandera no aparece en el log."""
    impl, pru = _par(
        f"def leer():\n    with open({SENUELO!r}) as f:\n        return f.read()\n",
        "from modulo import leer\n\ndef test_l():\n    leer()\n",
    )
    r = sandbox.ejecutar(impl, pru, timeout=30)
    assert not r.ok and config.BANDERA not in r.log


@sin_sandbox_exec
def test_sandbox_exec_niega_escribir_fuera(sin_revision, tmp_path):
    """Bajo el perfil, escribir fuera de la carpeta del sandbox falla; dentro se permite."""
    caja = tmp_path / "caja"
    caja.mkdir()
    fuera = tmp_path / "fuera.txt"
    impl, pru = _par(
        f"def esc():\n    with open({str(fuera)!r}, 'w') as f:\n        f.write('x')\n",
        "from modulo import esc\n\ndef test_e():\n    esc()\n",
    )
    r = sandbox.ejecutar(impl, pru, timeout=30, carpeta=caja)
    assert not r.ok and not fuera.exists()


@sin_sandbox_exec
def test_defensa_en_profundidad_importorskip(sin_revision):
    """Aun si la revisión estática se saltara, importorskip('os') para leer el señuelo falla."""
    impl, pru = _par(
        "VALOR = 1\n",
        "import pytest\nos = pytest.importorskip('os')\n\n"
        f"def test_d():\n    assert os.path.exists({SENUELO!r})\n"
        f"    open({SENUELO!r}).read()\n",
    )
    assert not sandbox.ejecutar(impl, pru, timeout=30).ok


def test_nodo_registra_en_el_log():
    """El nodo devuelve la ejecución y deja una línea «sandbox» en el log."""
    estado = {"hilo": "h", "implementacion": {**falso.IMPLEMENTACION, "sha256": "a"},
              "pruebas": {**falso.PRUEBAS, "sha256": "b"}}
    update = sandbox.nodo(estado)
    assert update["ejecucion"]["ok"] and update["ejecucion"]["evaluado"] == "a:b"
    assert log.leer()[0]["evento"] == "sandbox"
