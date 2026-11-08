"""El supervisor: decide el siguiente nodo con reglas explícitas que leen el estado.

«Con pasos conocidos, es más barato y más predecible» (M3, sesión 3, pág 18): el supervisor es
código, no un modelo. ``decidir`` es una función pura; el nodo la envuelve en un
``Command(update, goto)``, el mecanismo del supervisor del curso. Gana la primera regla que se
cumple (docs/diseno.md, sección 1.4). Ningún campo se borra: la vigencia se decide comparando
hashes.
"""

from typing import Literal

from langgraph.types import Command

from fabrica import config
from fabrica.estado import EstadoFabrica, evaluado, huella

Destino = Literal[
    "especificador", "aclarar", "planificador", "aprobar_plan", "implementador", "tester",
    "sandbox", "reviewer", "escalar", "documentador", "fin",
]
ABANICO = ["implementador", "tester"]


def _vigente(decision: dict | None, sha: str) -> bool:
    """Una decisión humana solo vale para lo que se le mostró a la persona."""
    return bool(decision) and decision.get("sobre_sha256") == sha


def veredicto_efectivo(estado: EstadoFabrica) -> tuple[str, bool]:
    """(«aprobar» | «corregir», anulado). El código anula un «aprobar» con pruebas fallidas."""
    revision = estado.get("revision") or {}
    ejecucion = estado.get("ejecucion") or {}
    if revision.get("veredicto") == "corregir":
        return "corregir", False
    if not ejecucion.get("ok"):
        return "corregir", True
    return "aprobar", False


def decidir(estado: EstadoFabrica) -> tuple[str | list[str], dict]:
    """El siguiente destino y el update del estado. Función pura: no llama a nada externo."""
    vueltas = estado.get("vueltas", 0)
    update: dict = {"vueltas": vueltas + 1}

    def ir(
        destino: str | list[str], regla: str, bitacora: list[str] | None = None, **extra
    ) -> tuple[str | list[str], dict]:
        nombre = " ∥ ".join(destino) if isinstance(destino, list) else destino
        linea = f"[supervisor] {regla} → {nombre}"
        return destino, {**update, **extra, "bitacora": (bitacora or []) + [linea]}

    def fin(final: str, motivo: str, regla: str, **extra) -> tuple[str, dict]:
        return ir("fin", regla, estado_final=final, motivo_final=motivo, **extra)

    # R0 · tope de vueltas
    if vueltas >= config.MAX_VUELTAS:
        return fin("ESCALAR A UNA PERSONA", "tope de vueltas", "R0")
    # R1 · un agente no cumplió su contrato tras sus intentos
    if estado.get("errores_agente"):
        agente = estado["errores_agente"][0]["agente"]
        return fin("ESCALAR A UNA PERSONA",
                   f"contrato inválido tras {config.MAX_INTENTOS} intentos: {agente}", "R1")
    # R2 · especificación
    esp = estado.get("especificacion")
    if not esp:
        return ir("especificador", "R2")
    # R3 · preguntas abiertas
    if esp.get("preguntas_abiertas"):
        decision = estado.get("decision_aclaracion")
        if not _vigente(decision, huella(esp)):
            return ir("aclarar", "R3")
        if decision["decision"] == "terminar":
            return fin("DETENIDA POR LA PERSONA", "la persona terminó en la aclaración", "R3")
        if decision["decision"] == "responder":
            return ir("especificador", "R3 · responder")
    # R4 · plan
    plan = estado.get("plan")
    if not plan:
        return ir("planificador", "R4")
    # R5 · aprobación del plan exacto
    decision_plan = estado.get("decision_plan")
    if not _vigente(decision_plan, huella(plan)):
        return ir("aprobar_plan", "R5")
    # R6 · la persona terminó
    if decision_plan["decision"] == "terminar":
        return fin("DETENIDA POR LA PERSONA", "la persona terminó en la aprobación del plan", "R6")
    # R7 · rechazo con tope
    if decision_plan["decision"] == "rechazar":
        if estado.get("rechazos_plan", 0) > config.MAX_RECHAZOS:
            return fin("ESCALAR A UNA PERSONA", "el plan no converge", "R7")
        return ir("planificador", "R7 · rechazo")
    # R8–R10 · implementador ∥ tester
    impl, pruebas = estado.get("implementacion"), estado.get("pruebas")
    if not impl and not pruebas:
        return ir(list(ABANICO), "R8 · abanico")
    if not impl:
        return ir("implementador", "R9")
    if not pruebas:
        return ir("tester", "R10")
    # R11 · ejecución del par vigente
    ejecucion = estado.get("ejecucion") or {}
    if ejecucion.get("evaluado") != evaluado(estado):
        return ir("sandbox", "R11")
    # R12 · revisión de esa ejecución
    revision = estado.get("revision") or {}
    if revision.get("evaluado") != ejecucion.get("evaluado"):
        return ir("reviewer", "R12")
    # R13 · corrección con tope
    veredicto, anulado = veredicto_efectivo(estado)
    notas = (["[supervisor] el reviewer dijo «aprobar» con pruebas fallidas: se anula"]
             if anulado else [])
    escalamiento = estado.get("decision_escalamiento")
    aceptado = _vigente(escalamiento, huella(revision)) and escalamiento["decision"] == "aceptar"
    if veredicto == "corregir" and not aceptado:
        ciclos = estado.get("ciclos_correccion", 0)
        if ciclos < config.MAX_CICLOS:
            responsable = revision.get("responsable") or "implementador"
            correccion = {
                "ciclo": ciclos + 1,
                "responsable": responsable,
                "criterio": revision.get("criterio"),
                "instruccion": revision.get("instruccion")
                or "Las pruebas fallan: corrige el código para que cumpla la especificación.",
                "observaciones": revision.get("observaciones", ""),
                "fallos": list(ejecucion.get("fallos", []))[:5],
            }
            return ir(responsable, f"R13 · corrección {ciclos + 1} de {config.MAX_CICLOS}",
                      correccion=correccion, ciclos_correccion=ciclos + 1, bitacora=notas)
        if not _vigente(escalamiento, huella(revision)):
            return ir("escalar", "R13 · tope de correcciones", bitacora=notas)
        return fin("DETENIDA POR LA PERSONA", "la persona terminó al escalar", "R13",
                   bitacora=notas)
    # R14 · documentación
    if not estado.get("documentacion"):
        return ir("documentador", "R14", bitacora=notas)
    # R15 · fin
    if aceptado:
        return fin("LISTA CON OBSERVACIONES", escalamiento.get("comentario", ""), "R15")
    return fin("LISTA", "flujo completo", "R15")


def nodo(estado: EstadoFabrica) -> Command[Destino]:
    """Nodo ``supervisor``: aplica ``decidir`` y devuelve ``Command(update, goto)``."""
    destino, update = decidir(estado)
    return Command(update=update, goto=destino)
