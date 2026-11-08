"""Las tres pausas humanas: aclarar, aprobar_plan y escalar (docs/diseno.md, sección 4).

Cada nodo solo arma el paquete que ve la persona, llama a ``interrupt`` y valida la respuesta. Al
reanudar, LangGraph vuelve a ejecutar el nodo desde el principio, así que nada con efectos va antes
del ``interrupt``: el registro en el log va después, cuando la respuesta ya es válida.

Falla cerrado: si la respuesta no es válida (operador fuera de la lista, sha256 distinto, decisión
que no corresponde), el nodo vuelve a pausar con los problemas y no escribe ninguna decisión.
"""

from langgraph.types import interrupt
from pydantic import ValidationError

from fabrica import config
from fabrica.contratos import (
    DECISIONES_POR_PAUSA,
    Plan,
    RespuestaHumana,
    problemas_pydantic,
    renderizar_plan,
    validar_respuesta,
)
from fabrica.estado import EstadoFabrica, huella
from fabrica.seguridad import log

EVENTO = {"aprobar": "aprobacion", "rechazar": "rechazo", "terminar": "rechazo",
          "continuar": "aclaracion", "responder": "aclaracion", "aceptar": "escalamiento"}


def opciones(pausa: str, estado: EstadoFabrica) -> list[str]:
    """Las decisiones posibles; «responder» solo mientras no se haya usado su tope."""
    posibles = list(DECISIONES_POR_PAUSA[pausa])
    if pausa == "aclaracion" and estado.get("aclaraciones", 0) >= config.MAX_ACLARACIONES:
        posibles.remove("responder")
    return posibles


def problemas_de_respuesta(
    respuesta: object, pausa: str, sha: str, permitidas: list[str]
) -> tuple[RespuestaHumana | None, list[str]]:
    """Valida el contrato, el operador, el sha256 y la decisión. Sin efectos."""
    try:
        resp = RespuestaHumana.model_validate(respuesta)
    except ValidationError as e:
        return None, problemas_pydantic(e)
    problemas = validar_respuesta(resp, pausa, sha, config.operadores_permitidos())
    if resp.decision not in permitidas and not any("no válida" in p for p in problemas):
        problemas.append(f"Decisión «{resp.decision}» no disponible; opciones: "
                         f"{', '.join(permitidas)}.")
    return resp, problemas


def _pausar(paquete: dict, estado: EstadoFabrica) -> RespuestaHumana:
    """Pausa hasta recibir una respuesta válida (cada intento es un ``interrupt`` aparte)."""
    problemas: list[str] = []
    while True:
        respuesta = interrupt({**paquete, "problemas": problemas})
        resp, problemas = problemas_de_respuesta(respuesta, paquete["pausa"], paquete["sha256"],
                                                 paquete["opciones"])
        if not problemas:
            return resp


def _registrar(resp: RespuestaHumana, estado: EstadoFabrica, nodo: str) -> None:
    """La decisión al log de seguridad: quién, qué, sobre qué sha256."""
    log.registrar(EVENTO[resp.decision], hilo=estado.get("hilo", ""), hu=estado.get("hu", ""),
                  capa="hitl", nodo=nodo, detalle=f"{resp.decision}: {resp.comentario}",
                  operador=resp.operador, usuario_so=log.usuario_so(), sha256=resp.sobre_sha256)


def paquete(pausa: str, estado: EstadoFabrica) -> dict:
    """Lo que ve la persona en cada pausa (función pura)."""
    base = {"pausa": pausa, "hilo": estado.get("hilo", ""), "hu": estado.get("hu", ""),
            "opciones": opciones(pausa, estado)}
    if pausa == "aclaracion":
        esp = estado["especificacion"]
        resumen = "\n".join(["**Preguntas abiertas del especificador**"]
                            + [f"- {p}" for p in esp.get("preguntas_abiertas", [])])
        return {**base, "titulo": "Aclarar la especificación", "resumen": resumen,
                "sha256": huella(esp),
                "contadores": {"aclaraciones": estado.get("aclaraciones", 0),
                               "max": config.MAX_ACLARACIONES}}
    if pausa == "plan":
        rechazos = estado.get("rechazos_plan", 0)
        aviso = ("\n\n**Aviso:** un rechazo más termina en ESCALAR A UNA PERSONA."
                 if rechazos >= config.MAX_RECHAZOS else "")
        return {**base, "titulo": "Aprobar el plan",
                "resumen": renderizar_plan(Plan.model_validate(estado["plan"])) + aviso,
                "sha256": huella(estado["plan"]),
                "contadores": {"rechazos": rechazos, "max": config.MAX_RECHAZOS}}
    revision = estado.get("revision") or {}
    ejecucion = estado.get("ejecucion") or {}
    resumen = "\n".join([
        f"**Criterio:** {revision.get('criterio')}",
        f"**Observaciones:** {revision.get('observaciones', '')}",
        f"**Pruebas:** {ejecucion.get('aprobadas', 0)} aprobadas, "
        f"{ejecucion.get('fallidas', 0)} fallidas, {ejecucion.get('errores', 0)} errores",
    ] + [f"- {f}" for f in ejecucion.get("fallos", [])[:5]])
    return {**base, "titulo": "Escalar: se agotaron las correcciones", "resumen": resumen,
            "sha256": huella(revision),
            "contadores": {"ciclos": estado.get("ciclos_correccion", 0), "max": config.MAX_CICLOS}}


def nodo_aclarar(estado: EstadoFabrica) -> dict:
    """Pausa para las preguntas abiertas: continuar, responder (máx. 1) o terminar."""
    resp = _pausar(paquete("aclaracion", estado), estado)
    _registrar(resp, estado, "aclarar")
    update: dict = {"decision_aclaracion": resp.model_dump(),
                    "bitacora": [f"[aclarar] {resp.decision} · {resp.operador}"]}
    if resp.decision == "responder":
        update["respuestas_aclaracion"] = resp.comentario
        update["aclaraciones"] = estado.get("aclaraciones", 0) + 1
    elif resp.decision == "continuar" and resp.comentario:
        # El comentario de «continuar» es guía para el planificador; sin esto se perdía y había
        # que rechazar el plan para reintroducirlo (hueco de la fase 4; diseño, sección 10.2).
        update["respuestas_aclaracion"] = resp.comentario
    return update


def nodo_aprobar_plan(estado: EstadoFabrica) -> dict:
    """Pausa para aprobar, rechazar (con comentario) o terminar el plan exacto que se mostró."""
    resp = _pausar(paquete("plan", estado), estado)
    _registrar(resp, estado, "aprobar_plan")
    update: dict = {"decision_plan": resp.model_dump(),
                    "bitacora": [f"[aprobar_plan] {resp.decision} · {resp.operador}"]}
    if resp.decision == "rechazar":
        update["rechazos_plan"] = estado.get("rechazos_plan", 0) + 1
    return update


def nodo_escalar(estado: EstadoFabrica) -> dict:
    """Pausa al tope de correcciones: aceptar con observaciones o terminar sin entregar."""
    resp = _pausar(paquete("escalamiento", estado), estado)
    _registrar(resp, estado, "escalar")
    return {"decision_escalamiento": resp.model_dump(),
            "bitacora": [f"[escalar] {resp.decision} · {resp.operador}"]}
