"""Sandbox: corre las pruebas generadas aisladas, sin Docker (docs/diseno.md, sección 5).

Primero repite la revisión estática (si falla, no ejecuta nada). Después escribe el código y las
pruebas en una carpeta temporal propia y corre pytest en un subproceso con entorno limpio,
``timeout`` y su propia sesión de procesos. El código generado nunca corre con ``exec()``.

Fase 2: versión básica. La fase 3 agrega los ``rlimit`` y ``sandbox-exec``.
"""

import os
import signal
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from fabrica.contratos import ResultadoEjecucion
from fabrica.seguridad.revision_codigo import revisar

TIMEOUT = 60
MAX_LOG = 4000
MAX_FALLO = 400
PYTEST_INI = "[pytest]\naddopts = -p no:cacheprovider\n"


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


def comando(carpeta: Path) -> list[str]:
    """pytest con el Python del proyecto, sin bytecode, sin site del usuario y sin caché."""
    return [
        sys.executable, "-B", "-s", "-m", "pytest", "-q", "-p", "no:cacheprovider",
        "-c", str(carpeta / "pytest.ini"), "--rootdir", str(carpeta),
        f"--junitxml={carpeta / 'resultados.xml'}",
    ]


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


def _correr(carpeta: Path, timeout: float) -> tuple[int | None, str]:
    """Corre pytest en su propia sesión; al vencer el tiempo mata a todo el grupo."""
    proceso = subprocess.Popen(
        comando(carpeta), cwd=carpeta, env=entorno_limpio(carpeta), stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True,
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
    inicio = time.monotonic()
    codigo, salida = _correr(carpeta, timeout)
    segundos = round(time.monotonic() - inicio, 2)
    aprobadas, fallidas, errores, fallos = _leer_junit(carpeta / "resultados.xml")
    if codigo is None:
        errores += 1
        fallos.append(f"TIMEOUT: las pruebas pasaron de {timeout} s.")
    ok = codigo == 0 and fallidas == 0 and errores == 0 and aprobadas > 0
    return ResultadoEjecucion(
        ok=ok, evaluado=evaluado, aprobadas=aprobadas, fallidas=fallidas, errores=errores,
        segundos=segundos, fallos=fallos[:20], log=salida[-MAX_LOG:], aislamiento="subproceso",
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
