"""Sandbox: corre las pruebas generadas aisladas, sin Docker (docs/diseno.md, sección 5).

Primero repite la revisión estática (si falla, no ejecuta nada). Después escribe el código y las
pruebas en una carpeta temporal propia y corre pytest en un subproceso con entorno limpio,
``timeout``, su propia sesión de procesos y ``rlimit`` (CPU, tamaño de archivo y descriptores). El
código generado nunca corre con ``exec()``.

En macOS, si la sonda de ``sandbox-exec`` pasa, pytest corre además dentro de un perfil que niega la
red, la escritura fuera de la carpeta temporal y la lectura del señuelo, de ``.env`` y de
``datos/``. ``sandbox-exec`` está obsoleto en Apple y puede desaparecer: por eso es la segunda capa,
detrás de la revisión estática con lista blanca, y se salta si la sonda falla.
"""

import os
import resource
import signal
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path

from fabrica import config
from fabrica.contratos import ResultadoEjecucion
from fabrica.seguridad.revision_codigo import revisar

TIMEOUT = 60
MAX_LOG = 4000
MAX_FALLO = 400
PYTEST_INI = "[pytest]\naddopts = -p no:cacheprovider\n"

# Límites por recurso (docs/diseno.md, sección 5). Sin RLIMIT_NPROC: en macOS cuenta todos los
# procesos del usuario, no solo los del sandbox. RLIMIT_AS no se respeta en macOS.
CPU_SEGUNDOS = 30
FSIZE_BYTES = 5 * 1024 * 1024
NOFILE = 128
SANDBOX_EXEC = "/usr/bin/sandbox-exec"


def entorno_limpio(carpeta: Path) -> dict:
    """Entorno mínimo: sin secretos, sin PYTHONPATH y con HOME y TMPDIR en la carpeta temporal."""
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": str(carpeta),
        "TMPDIR": str(carpeta),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "LANG": "C.UTF-8",
    }


def _limites() -> None:
    """``preexec_fn``: nueva sesión y ``rlimit`` de CPU, tamaño de archivo y descriptores."""
    os.setsid()
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_SEGUNDOS, CPU_SEGUNDOS))
    resource.setrlimit(resource.RLIMIT_FSIZE, (FSIZE_BYTES, FSIZE_BYTES))
    resource.setrlimit(resource.RLIMIT_NOFILE, (NOFILE, NOFILE))


def perfil_sandbox(carpeta: Path) -> str:
    """Perfil SBPL: niega la red, la escritura fuera de la carpeta y la lectura de lo sensible."""
    tmp = str(carpeta.resolve())
    senuelo = str((config.RAIZ / "secretos_demo.txt").resolve())
    env = str((config.RAIZ / ".env").resolve())
    datos = str(config.ruta_db().resolve().parent)
    return (
        "(version 1)\n"
        "(allow default)\n"
        "(deny network*)\n"
        "(deny file-write*)\n"
        f'(allow file-write* (subpath "{tmp}") (subpath "/dev"))\n'
        f'(deny file-read* (subpath "{datos}") (literal "{senuelo}") (literal "{env}"))\n'
    )


@lru_cache(maxsize=1)
def sandbox_exec_disponible() -> bool:
    """¿Existe ``sandbox-exec`` y deja correr el Python del proyecto bajo el perfil? (se cachea)."""
    if not Path(SANDBOX_EXEC).exists():
        return False
    try:
        with tempfile.TemporaryDirectory(prefix="fabrica-sonda-") as tmp:
            carpeta = Path(tmp)
            cmd = [SANDBOX_EXEC, "-p", perfil_sandbox(carpeta),
                   sys.executable, "-I", "-c", "print('ok')"]
            r = subprocess.run(cmd, cwd=carpeta, env=entorno_limpio(carpeta),
                               capture_output=True, text=True, timeout=30,
                               stdin=subprocess.DEVNULL)
        return r.returncode == 0 and "ok" in r.stdout
    except (OSError, subprocess.SubprocessError):
        return False


def comando(carpeta: Path, usar_sandbox_exec: bool = False) -> list[str]:
    """pytest con el Python del proyecto, sin bytecode, sin site del usuario y sin caché."""
    base = [
        sys.executable, "-B", "-s", "-m", "pytest", "-q", "-p", "no:cacheprovider",
        "-c", str(carpeta / "pytest.ini"), "--rootdir", str(carpeta),
        f"--junitxml={carpeta / 'resultados.xml'}",
    ]
    if usar_sandbox_exec:
        return [SANDBOX_EXEC, "-p", perfil_sandbox(carpeta), *base]
    return base


def _leer_junit(ruta: Path) -> tuple[int, int, int, list[str]]:
    """(aprobadas, fallidas, errores, fallos) desde el JUnit XML de pytest."""
    if not ruta.exists():
        return 0, 0, 0, []
    raiz = ET.parse(ruta).getroot()
    casos = list(raiz.iter("testcase"))
    fallidas = errores = 0
    fallos = []
    for caso in casos:
        for tipo in ("failure", "error"):
            nodo = caso.find(tipo)
            if nodo is not None:
                fallidas += tipo == "failure"
                errores += tipo == "error"
                mensaje = (nodo.get("message") or nodo.text or "").strip()
                fallos.append(f"{caso.get('classname')}::{caso.get('name')}: "
                              f"{mensaje[:MAX_FALLO]}")
    saltadas = sum(1 for c in casos if c.find("skipped") is not None)
    # Un error de colección aparece como <error> en un testcase sin nombre de prueba real.
    return len(casos) - fallidas - errores - saltadas, fallidas, errores, fallos


def _correr(carpeta: Path, timeout: float, usar_sandbox_exec: bool) -> tuple[int | None, str]:
    """Corre pytest en su propia sesión con ``rlimit``; al vencer el tiempo mata a todo el grupo."""
    proceso = subprocess.Popen(
        comando(carpeta, usar_sandbox_exec), cwd=carpeta, env=entorno_limpio(carpeta),
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        preexec_fn=_limites,
    )
    try:
        salida, _ = proceso.communicate(timeout=timeout)
        return proceso.returncode, salida
    except subprocess.TimeoutExpired:
        os.killpg(proceso.pid, signal.SIGKILL)
        salida, _ = proceso.communicate()
        return None, (salida or "") + f"\nTIMEOUT: las pruebas pasaron de {timeout} s."


def ejecutar(
    implementacion: dict,
    pruebas: dict,
    evaluado: str = "",
    *,
    timeout: float = TIMEOUT,
    carpeta: Path | None = None,
) -> ResultadoEjecucion:
    """Revisa y ejecuta. ``carpeta`` permite a las pruebas inspeccionar lo que queda en disco."""
    archivos_impl = implementacion.get("archivos", [])
    archivos_pru = pruebas.get("archivos", [])
    propios = [a["nombre"][:-3] for a in archivos_impl]
    problemas = revisar(archivos_impl, "implementacion", propios)
    problemas += revisar(archivos_pru, "pruebas", propios)
    if problemas:
        return ResultadoEjecucion(ok=False, evaluado=evaluado, problemas_estaticos=problemas,
                                  log="No se ejecutó: la revisión estática encontró problemas.")
    if carpeta is None:
        with tempfile.TemporaryDirectory(prefix="fabrica-sandbox-") as tmp:
            return ejecutar(implementacion, pruebas, evaluado, timeout=timeout, carpeta=Path(tmp))
    for archivo in archivos_impl + archivos_pru:
        (carpeta / archivo["nombre"]).write_text(archivo["contenido"], encoding="utf-8")
    (carpeta / "pytest.ini").write_text(PYTEST_INI, encoding="utf-8")
    usar_sandbox_exec = sandbox_exec_disponible()
    inicio = time.monotonic()
    codigo, salida = _correr(carpeta, timeout, usar_sandbox_exec)
    segundos = round(time.monotonic() - inicio, 2)
    aprobadas, fallidas, errores, fallos = _leer_junit(carpeta / "resultados.xml")
    if codigo is None:
        errores += 1
        fallos.append(f"TIMEOUT: las pruebas pasaron de {timeout} s.")
    ok = codigo == 0 and fallidas == 0 and errores == 0 and aprobadas > 0
    return ResultadoEjecucion(
        ok=ok, evaluado=evaluado, aprobadas=aprobadas, fallidas=fallidas, errores=errores,
        segundos=segundos, fallos=fallos[:20], log=salida[-MAX_LOG:],
        aislamiento="sandbox-exec" if usar_sandbox_exec else "subproceso",
    )


def nodo(estado: dict) -> dict:
    """Nodo ``sandbox`` del grafo: ejecuta el par vigente y registra el resultado en el log."""
    from fabrica.estado import evaluado as huella_evaluado
    from fabrica.seguridad import log

    evaluado = huella_evaluado(estado)
    r = ejecutar(estado.get("implementacion") or {}, estado.get("pruebas") or {}, evaluado)
    if r.problemas_estaticos:
        detalle = "no ejecutado: " + " | ".join(r.problemas_estaticos)
    else:
        detalle = f"{r.aprobadas} aprobadas, {r.fallidas} fallidas, {r.errores} errores"
    log.registrar("sandbox", hilo=estado.get("hilo", ""), hu=estado.get("hu", ""),
                  capa="sandbox", nodo="sandbox", detalle=detalle)
    return {"ejecucion": r.model_dump(),
            "bitacora": [f"[sandbox] {'OK' if r.ok else 'FALLA'} · {detalle} · {r.segundos} s"]}
