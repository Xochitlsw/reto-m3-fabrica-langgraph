"""Estado compartido del grafo (docs/diseno.md, sección 2).

Solo guarda tipos primitivos: cada contrato se guarda con ``model_dump()`` y se vuelve a validar al
leerlo. Así funciona el modo estricto de msgpack del checkpointer y así lo hace el curso (Pydantic
solo en los contratos). Cada campo tiene un solo escritor; los que se acumulan llevan reductor.
"""

import hashlib
import json
import operator
from typing import Annotated, Any, TypedDict


class EstadoFabrica(TypedDict, total=False):
    """Estado de una corrida de la fábrica, identificada por su hilo (``thread_id``)."""

    # CLI
    hilo: str
    historia_ruta: str
    modelo: str  # "real" o "falso:<escenario>"
    # guardian
    historia_texto: str
    historia_sha256: str
    hu: str
    defensas: bool
    # guardian y filtro (en pasos distintos)
    seguridad: dict
    # agentes y pausas
    especificacion: dict
    decision_aclaracion: dict
    respuestas_aclaracion: str
    aclaraciones: int
    plan: dict
    decision_plan: dict
    rechazos_plan: int
    implementacion: dict
    pruebas: dict
    ejecucion: dict
    revision: dict
    decision_escalamiento: dict
    documentacion: dict
    # supervisor
    correccion: dict
    ciclos_correccion: int
    vueltas: int
    estado_final: str
    motivo_final: str
    # acumulados
    bitacora: Annotated[list[str], operator.add]
    costo_usd: Annotated[float, operator.add]
    llamadas: Annotated[list[dict], operator.add]
    errores_agente: Annotated[list[dict], operator.add]


def huella(dato: Any) -> str:
    """sha256 estable de un dato primitivo (JSON con claves ordenadas)."""
    texto = json.dumps(dato, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def evaluado(estado: EstadoFabrica) -> str:
    """Huella del par implementación + pruebas que se ejecuta y se revisa."""
    impl = estado.get("implementacion") or {}
    pru = estado.get("pruebas") or {}
    return f"{impl.get('sha256', '')}:{pru.get('sha256', '')}"
