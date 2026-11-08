"""Log de seguridad en JSON Lines (``logs/seguridad.jsonl``).

Cada bloqueo, alerta, salida rechazada, ejecución en sandbox y decisión humana deja una línea. Nunca
guarda el texto completo de la historia: el detalle se recorta a 300 caracteres. El log sigue
encendido aunque ``DEFENSAS=0``, para que la demo del ataque deje rastro.
"""

import getpass
import json
from datetime import UTC, datetime

from fabrica import config

EVENTOS = (
    "bloqueo",
    "alerta",
    "salida_rechazada",
    "sandbox",
    "aprobacion",
    "rechazo",
    "aclaracion",
    "escalamiento",
    "defensas_desactivadas",
    "respuesta_rechazada",
)
CLAVES = ("ts", "evento", "hilo", "hu", "capa", "nodo", "detalle")
MAX_DETALLE = 300


def usuario_so() -> str:
    """El usuario del sistema operativo que corre la CLI."""
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001 - sin usuario no se debe romper el log
        return "desconocido"


def registrar(
    evento: str,
    *,
    hilo: str = "",
    hu: str = "",
    capa: str = "",
    nodo: str = "",
    detalle: str = "",
    **extra: str | int | None,
) -> dict:
    """Agrega una línea al log y la devuelve. ``extra`` admite operador, usuario_so y sha256."""
    if evento not in EVENTOS:
        raise ValueError(f"Evento de seguridad desconocido: {evento}")
    linea = {
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "evento": evento,
        "hilo": hilo,
        "hu": hu,
        "capa": capa,
        "nodo": nodo,
        "detalle": " ".join(str(detalle).split())[:MAX_DETALLE],
    }
    linea.update({k: v for k, v in extra.items() if v is not None})
    ruta = config.ruta_log()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("a", encoding="utf-8") as f:
        f.write(json.dumps(linea, ensure_ascii=False) + "\n")
    return linea


def leer(hilo: str | None = None) -> list[dict]:
    """Las líneas del log, opcionalmente solo las de un hilo."""
    ruta = config.ruta_log()
    if not ruta.exists():
        return []
    lineas = [json.loads(x) for x in ruta.read_text(encoding="utf-8").splitlines() if x.strip()]
    return [x for x in lineas if hilo is None or x.get("hilo") == hilo]
