"""Paso 9: las tres pausas con interrupt + Command(resume) e InMemorySaver."""

import copy

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from fabrica import falso, humano
from fabrica.estado import EstadoFabrica, huella
from fabrica.seguridad import log


def _grafo(nodo):
    g = StateGraph(EstadoFabrica)
    g.add_node("pausa", nodo)
    g.add_edge(START, "pausa")
    g.add_edge("pausa", END)
    return g.compile(checkpointer=InMemorySaver())


def _respuesta(pausa, decision, sobre, operador="xochitl", comentario=""):
    return {"pausa": pausa, "decision": decision, "comentario": comentario,
            "operador": operador, "sobre_sha256": huella(sobre)}


@pytest.fixture
def estado():
    """Estado con especificación (con una pregunta), plan y una revisión."""
    esp = copy.deepcopy(falso.ESPECIFICACION)
    esp["preguntas_abiertas"] = ["¿orden?"]
    return {"hilo": "h1", "hu": "HU-05", "especificacion": esp, "plan": copy.deepcopy(falso.PLAN),
            "revision": {"criterio": "C-01", "observaciones": "falla", "veredicto": "corregir"},
            "ejecucion": {"aprobadas": 5, "fallidas": 1, "fallos": ["test_cp02"]},
            "ciclos_correccion": 2}


def test_aprobar_plan_pausa_y_reanuda(estado):
    """Pausa → nada en el log → Command(resume) → decisión y una línea en el log."""
    app = _grafo(humano.nodo_aprobar_plan)
    cfg = {"configurable": {"thread_id": "t1"}}
    salida = app.invoke(estado, cfg)
    paquete = salida["__interrupt__"][0].value
    assert paquete["pausa"] == "plan" and paquete["sha256"] == huella(estado["plan"])
    assert "calcular_antiguedad" in paquete["resumen"] and paquete["contadores"]["rechazos"] == 0
    assert app.get_state(cfg).next == ("pausa",)
    assert log.leer() == []  # nada se ejecuta antes del interrupt
    final = app.invoke(Command(resume=_respuesta("plan", "aprobar", estado["plan"])), cfg)
    assert final["decision_plan"]["decision"] == "aprobar"
    lineas = log.leer()
    assert len(lineas) == 1 and lineas[0]["evento"] == "aprobacion"
    assert lineas[0]["operador"] == "xochitl" and lineas[0]["sha256"] == huella(estado["plan"])
    assert lineas[0]["usuario_so"]


def test_rechazo_cuenta(estado):
    """Rechazar con comentario suma un rechazo y queda como «rechazo» en el log."""
    app = _grafo(humano.nodo_aprobar_plan)
    cfg = {"configurable": {"thread_id": "t2"}}
    app.invoke(estado, cfg)
    final = app.invoke(Command(resume=_respuesta("plan", "rechazar", estado["plan"],
                                                 comentario="cubre el día 31")), cfg)
    assert final["rechazos_plan"] == 1 and final["decision_plan"]["comentario"] == "cubre el día 31"
    assert log.leer()[0]["evento"] == "rechazo"


@pytest.mark.parametrize("operador, sobre, problema", [
    ("intruso", None, "intruso"),
    ("xochitl", {"otro": "plan"}, "sha256"),
])
def test_respuesta_invalida_falla_cerrado(estado, operador, sobre, problema):
    """Operador fuera de la lista o sha distinto: sigue en pausa y no escribe decisión."""
    app = _grafo(humano.nodo_aprobar_plan)
    cfg = {"configurable": {"thread_id": "t3"}}
    app.invoke(estado, cfg)
    mala = _respuesta("plan", "aprobar", sobre or estado["plan"], operador=operador)
    salida = app.invoke(Command(resume=mala), cfg)
    assert any(problema in p for p in salida["__interrupt__"][0].value["problemas"])
    assert "decision_plan" not in app.get_state(cfg).values
    assert app.get_state(cfg).next == ("pausa",) and log.leer() == []
    # Después, una respuesta válida sí reanuda.
    final = app.invoke(Command(resume=_respuesta("plan", "aprobar", estado["plan"])), cfg)
    assert final["decision_plan"]["operador"] == "xochitl" and len(log.leer()) == 1


def test_contrato_invalido_falla_cerrado(estado):
    """Una respuesta que ni siquiera cumple el contrato tampoco reanuda."""
    app = _grafo(humano.nodo_aprobar_plan)
    cfg = {"configurable": {"thread_id": "t4"}}
    app.invoke(estado, cfg)
    salida = app.invoke(Command(resume={"decision": "aprobar"}), cfg)
    assert "El JSON no cumple" in salida["__interrupt__"][0].value["problemas"][0]


def test_aclarar_responder_una_vez(estado):
    """Responder guarda las respuestas y suma una aclaración; después ya no se ofrece."""
    app = _grafo(humano.nodo_aclarar)
    cfg = {"configurable": {"thread_id": "t5"}}
    paquete = app.invoke(estado, cfg)["__interrupt__"][0].value
    assert paquete["opciones"] == ["continuar", "responder", "terminar"]
    assert "¿orden?" in paquete["resumen"]
    final = app.invoke(Command(resume=_respuesta("aclaracion", "responder",
                                                 estado["especificacion"],
                                                 comentario="de mayor a menor")), cfg)
    assert final["respuestas_aclaracion"] == "de mayor a menor" and final["aclaraciones"] == 1
    assert log.leer()[0]["evento"] == "aclaracion"
    assert humano.opciones("aclaracion", final) == ["continuar", "terminar"]


def test_aclarar_responder_agotado(estado):
    """Con la aclaración usada, «responder» se rechaza y la pausa sigue."""
    estado["aclaraciones"] = 1
    app = _grafo(humano.nodo_aclarar)
    cfg = {"configurable": {"thread_id": "t6"}}
    app.invoke(estado, cfg)
    salida = app.invoke(Command(resume=_respuesta("aclaracion", "responder",
                                                  estado["especificacion"],
                                                  comentario="otra")), cfg)
    assert any("no disponible" in p for p in salida["__interrupt__"][0].value["problemas"])


def test_escalar_aceptar(estado):
    """Escalar muestra la revisión y los fallos; aceptar exige comentario y lo registra."""
    app = _grafo(humano.nodo_escalar)
    cfg = {"configurable": {"thread_id": "t7"}}
    paquete = app.invoke(estado, cfg)["__interrupt__"][0].value
    assert paquete["opciones"] == ["aceptar", "terminar"] and "test_cp02" in paquete["resumen"]
    assert paquete["contadores"] == {"ciclos": 2, "max": 2}
    sin_comentario = _respuesta("escalamiento", "aceptar", estado["revision"])
    salida = app.invoke(Command(resume=sin_comentario), cfg)
    assert any("comentario" in p for p in salida["__interrupt__"][0].value["problemas"])
    final = app.invoke(Command(resume=_respuesta("escalamiento", "aceptar", estado["revision"],
                                                 comentario="falta el 29 de febrero")), cfg)
    assert final["decision_escalamiento"]["decision"] == "aceptar"
    assert log.leer()[0]["evento"] == "escalamiento"


def test_aviso_en_el_ultimo_rechazo(estado):
    """Con 2 rechazos, el paquete avisa que otro rechazo escala."""
    estado["rechazos_plan"] = 2
    assert "ESCALAR" in humano.paquete("plan", estado)["resumen"]
