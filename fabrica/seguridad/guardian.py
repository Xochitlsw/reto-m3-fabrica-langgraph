"""Guardián de entrada, capa 1 (reglas en código, gratis y siempre).

Fase 2: versión mínima, con la ruta y el tamaño. La fase 3 agrega UTF-8 estricto, caracteres de
control, Unicode oculto y los patrones de inyección (docs/diseno.md, sección 5).

La ruta se revisa antes de leer nada: un archivo fuera de ``historias/`` (por ejemplo, el señuelo)
nunca se abre.
"""

import hashlib
import re
from pathlib import Path

from fabrica import config
from fabrica.estado import EstadoFabrica
from fabrica.seguridad import log

MAX_BYTES = 8 * 1024
NOMBRE_HISTORIA = re.compile(r"^(HU-\d{2})-[a-z0-9-]+\.md$")


def revisar_ruta(ruta_texto: str) -> tuple[Path | None, list[str]]:
    """La ruta resuelta si es una historia permitida, o los problemas. No lee el contenido."""
    ruta = Path(ruta_texto)
    if not ruta.is_absolute():
        ruta = Path.cwd() / ruta
    if ruta.is_symlink():
        return None, ["La historia es un enlace simbólico."]
    resuelta = ruta.resolve()
    carpeta = config.ruta_historias().resolve()
    if carpeta not in resuelta.parents:
        return None, [f"La ruta está fuera de {carpeta.name}/."]
    if not NOMBRE_HISTORIA.match(resuelta.name):
        return None, ["El nombre no tiene la forma HU-NN-nombre.md."]
    if not resuelta.is_file():
        return None, ["La historia no existe."]
    if resuelta.stat().st_size > MAX_BYTES:
        return None, [f"La historia pasa de {MAX_BYTES} bytes."]
    return resuelta, []


def nodo(estado: EstadoFabrica) -> dict:
    """Nodo ``guardian``: valida la entrada y la deja en el estado, o la bloquea."""
    hilo = estado.get("hilo", "")
    defensas = config.defensas_activas()
    ruta, problemas = revisar_ruta(estado.get("historia_ruta", ""))
    texto = ""
    if ruta is not None:
        try:
            texto = ruta.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            problemas = ["La historia no está en UTF-8."]
    hu = ""
    if ruta is not None:
        coincide = NOMBRE_HISTORIA.match(ruta.name)
        hu = coincide.group(1) if coincide else ""
    seguridad = {"bloqueada": bool(problemas), "capa": "reglas", "motivos": problemas,
                 "marcas": []}
    if problemas:
        log.registrar("bloqueo", hilo=hilo, hu=hu, capa="reglas", nodo="guardian",
                      detalle=" | ".join(problemas))
    if not defensas:
        log.registrar("defensas_desactivadas", hilo=hilo, hu=hu, capa="reglas", nodo="guardian",
                      detalle="DEFENSAS=0: el filtro con modelo no se ejecuta")
    resumen = (f"BLOQUEADA · {' | '.join(problemas)}" if problemas
               else f"OK · {len(texto.encode('utf-8'))} bytes")
    return {
        "historia_texto": texto,
        "historia_sha256": hashlib.sha256(texto.encode("utf-8")).hexdigest(),
        "hu": hu,
        "defensas": defensas,
        "seguridad": seguridad,
        "bitacora": [f"[guardian] {resumen}"],
    }
