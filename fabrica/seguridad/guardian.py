"""Guardián de entrada, capa 1 (reglas en código, gratis y siempre).

Revisa, sin llamar al modelo (docs/diseno.md, sección 5): la ruta (dentro de ``historias/``, con
nombre ``HU-NN-slug.md``, sin enlace simbólico), el tamaño, UTF-8 estricto, caracteres de control,
Unicode oculto o bidireccional y los patrones de inyección (normalizados con NFKC y sin distinguir
mayúsculas). Marca, sin bloquear, las URLs y los bloques de código.

La ruta se revisa antes de leer nada: un archivo fuera de ``historias/`` (por ejemplo, el señuelo)
nunca se abre.
"""

import hashlib
import re
import unicodedata
from pathlib import Path

from fabrica import config
from fabrica.estado import EstadoFabrica
from fabrica.seguridad import log

MAX_BYTES = 8 * 1024
NOMBRE_HISTORIA = re.compile(r"^(HU-\d{2})-[a-z0-9-]+\.md$")

# Caracteres de control permitidos: salto de línea, tabulador y retorno de carro.
CONTROL_PERMITIDOS = frozenset("\n\t\r")
# Rangos Unicode invisibles o de control bidireccional (ocultan texto o invierten el orden).
RANGOS_OCULTOS = (
    (0x200B, 0x200F),  # espacios de ancho cero y marcas LRM/RLM
    (0x202A, 0x202E),  # incrustaciones y anulaciones bidireccionales
    (0x2066, 0x2069),  # aislamientos direccionales
    (0xFEFF, 0xFEFF),  # espacio de ancho cero sin salto (BOM incrustado)
)
# Patrones de inyección. Se buscan sobre el texto normalizado con NFKC y en minúsculas.
PATRONES = (
    (re.compile(r"ignora[^.\n]{0,40}instruc"), "instrucción de ignorar las reglas"),
    (re.compile(r"asistente de (ia|inteligencia artificial)"), "mención a un asistente de IA"),
    (re.compile(r"system prompt"), "mención al «system prompt»"),
    (re.compile(r"os\.environ"), "acceso a variables de entorno (os.environ)"),
    (re.compile(r"subprocess"), "ejecución de comandos (subprocess)"),
    (re.compile(r"\b(eval|exec)\s*\("), "llamada a eval()/exec()"),
    (re.compile(r"\.env\b"), "referencia a .env"),
    (re.compile(r"secretos"), "referencia a «secretos»"),
    (re.compile(re.escape(config.BANDERA.lower())), "referencia a la bandera del señuelo"),
    (re.compile(r"\.\./"), "ruta relativa hacia arriba (../)"),
    (re.compile(r"</?\s*historia"), "etiqueta </historia…> incrustada"),
)
# Patrones que solo se marcan (no bloquean): se anotan para que la persona los vea.
MARCAS = (
    (re.compile(r"https?://"), "URL"),
    (re.compile(r"```"), "bloque de código"),
)


def _normalizar(texto: str) -> str:
    """NFKC y minúsculas, para que un patrón no se escape con variantes Unicode o mayúsculas."""
    return unicodedata.normalize("NFKC", texto).casefold()


def _caracter_oculto(cp: int) -> bool:
    """¿El punto de código está en un rango invisible o bidireccional?"""
    return any(inicio <= cp <= fin for inicio, fin in RANGOS_OCULTOS)


def revisar_texto(texto: str) -> tuple[list[str], list[str]]:
    """Problemas que bloquean y marcas que solo se anotan, para un texto ya decodificado."""
    problemas: list[str] = []
    for ch in texto:
        if ch in CONTROL_PERMITIDOS:
            continue
        if unicodedata.category(ch) == "Cc":
            problemas.append(f"carácter de control U+{ord(ch):04X}")
            break
    if any(_caracter_oculto(ord(ch)) for ch in texto):
        problemas.append("carácter Unicode oculto o bidireccional")
    normal = _normalizar(texto)
    for patron, motivo in PATRONES:
        if patron.search(normal):
            problemas.append(motivo)
    marcas = [etiqueta for patron, etiqueta in MARCAS if patron.search(texto)]
    return problemas, marcas


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
    marcas: list[str] = []
    if ruta is not None:
        try:
            texto = ruta.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            problemas = ["La historia no está en UTF-8."]
        else:
            # La detección de inyección de contenido es parte de las «defensas» y se apaga con
            # DEFENSAS=0 (demo). El límite de ruta/tamaño/UTF-8 de revisar_ruta nunca se apaga:
            # es el que impide leer el señuelo, y HU-99 es una ruta válida que igual lo pasa.
            if defensas:
                problemas_texto, marcas = revisar_texto(texto)
                problemas += problemas_texto
    hu = ""
    if ruta is not None:
        coincide = NOMBRE_HISTORIA.match(ruta.name)
        hu = coincide.group(1) if coincide else ""
    seguridad = {"bloqueada": bool(problemas), "capa": "reglas", "motivos": problemas,
                 "marcas": marcas}
    if problemas:
        log.registrar("bloqueo", hilo=hilo, hu=hu, capa="reglas", nodo="guardian",
                      detalle=" | ".join(problemas))
    elif marcas:
        log.registrar("alerta", hilo=hilo, hu=hu, capa="reglas", nodo="guardian",
                      detalle="marcas: " + ", ".join(marcas))
    if not defensas:
        log.registrar("defensas_desactivadas", hilo=hilo, hu=hu, capa="reglas", nodo="guardian",
                      detalle="DEFENSAS=0: sin detección de inyección ni filtro con modelo")
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
