"""Rutas, topes y constantes de la fábrica.

Las rutas se leen de variables de entorno en cada llamada para que las pruebas (y los subprocesos de
la CLI) puedan redirigirlas a carpetas temporales sin tocar los archivos reales.
"""

import json
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PROMPTS = Path(__file__).resolve().parent / "prompts"

# Topes (docs/diseno.md, sección 1.4). Todo bucle tiene un límite.
MAX_VUELTAS = 40
MAX_RECHAZOS = 2
MAX_CICLOS = 2
MAX_ACLARACIONES = 1
MAX_INTENTOS = 2
MAX_CODIGO_ESTADO = 64 * 1024

# El señuelo nunca se lee: basta con la constante para detectar una fuga.
BANDERA = "BANDERA-DEMO"

ESTADOS_FINALES = (
    "LISTA",
    "LISTA CON OBSERVACIONES",
    "BLOQUEADA POR SEGURIDAD",
    "DETENIDA POR LA PERSONA",
    "ESCALAR A UNA PERSONA",
)


def _ruta(variable: str, por_omision: Path) -> Path:
    """Ruta tomada de una variable de entorno, o la ruta por omisión."""
    valor = os.environ.get(variable)
    return Path(valor) if valor else por_omision


def ruta_reglas() -> Path:
    """Archivo de reglas de negocio que lee el especificador y su validador."""
    return _ruta("FABRICA_REGLAS", RAIZ / "contexto" / "reglas_negocio.md")


def ruta_historias() -> Path:
    """Carpeta permitida para las historias de usuario."""
    return _ruta("FABRICA_HISTORIAS", RAIZ / "historias")


def ruta_operadores() -> Path:
    """Lista permitida de operadores que pueden decidir en una pausa humana."""
    return _ruta("FABRICA_OPERADORES", RAIZ / "config" / "operadores.json")


def ruta_log() -> Path:
    """Log de seguridad (JSON Lines)."""
    return _ruta("FABRICA_LOG", RAIZ / "logs" / "seguridad.jsonl")


def ruta_salida() -> Path:
    """Carpeta donde la fábrica escribe lo generado, una subcarpeta por hilo."""
    return _ruta("FABRICA_SALIDA", RAIZ / "salida")


def ruta_evidencia() -> Path:
    """Carpeta de evidencia de las corridas reales."""
    return _ruta("FABRICA_EVIDENCIA", RAIZ / "evidencia" / "corridas")


def ruta_db() -> Path:
    """Base SQLite de los checkpoints."""
    return _ruta("FABRICA_DB", RAIZ / "datos" / "checkpoints.sqlite")


def operadores_permitidos() -> list[str]:
    """Ids de operador permitidos; una lista vacía si el archivo no existe o no es válido."""
    try:
        datos = json.loads(ruta_operadores().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [str(x) for x in datos] if isinstance(datos, list) else []


def defensas_activas() -> bool:
    """False solo con DEFENSAS=0 (demo del ataque): apaga las dos capas del guardián."""
    return os.environ.get("DEFENSAS", "1") != "0"
