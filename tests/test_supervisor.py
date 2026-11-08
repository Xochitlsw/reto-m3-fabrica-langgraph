"""Paso 8: una fila por regla del supervisor (R0–R15), topes y anulación del «aprobar»."""

import copy

import pytest
from langgraph.types import Command

from fabrica import config, falso, supervisor
from fabrica.estado import huella
from fabrica.supervisor import decidir


def _decision(pausa: str, decision: str, sobre: dict, comentario: str = "") -> dict:
    return {"pausa": pausa, "decision": decision, "comentario": comentario,
            "operador": "xochitl", "sobre_sha256": huella(sobre)}


def _base() -> dict:
    """Estado con especificación y plan aprobado."""
    esp = copy.deepcopy(falso.ESPECIFICACION)
    plan = copy.deepcopy(falso.PLAN)
    return {"especificacion": esp, "plan": plan,
            "decision_plan": _decision("plan", "aprobar", plan)}


def _con_ejecucion(ok: bool, veredicto: str = "aprobar", responsable: str | None = None) -> dict:
    """Estado con implementación, pruebas, ejecución y revisión vigentes."""
    e = _base()
    e["implementacion"] = {"archivos": [], "sha256": "i"}
    e["pruebas"] = {"archivos": [], "casos": [], "sha256": "p"}
    e["ejecucion"] = {"ok": ok, "evaluado": "i:p", "fallos": ["test_cp02: assert"]}
    e["revision"] = {"veredicto": veredicto, "responsable": responsable, "criterio": "C-01",
                     "instruccion": "arregla" if veredicto == "corregir" else "",
                     "observaciones": "obs", "evaluado": "i:p"}
    return e


def test_r0_tope_de_vueltas():
    """R0: con 40 vueltas, fin · ESCALAR."""
    destino, up = decidir({"vueltas": config.MAX_VUELTAS})
    assert destino == "fin" and up["estado_final"] == "ESCALAR A UNA PERSONA"
    assert up["motivo_final"] == "tope de vueltas"


def test_r1_errores_agente():
    """R1: errores_agente → fin · ESCALAR, nombrando al agente."""
    destino, up = decidir({"errores_agente": [{"agente": "planificador", "problemas": []}]})
    assert destino == "fin" and "planificador" in up["motivo_final"]


def test_r2_sin_especificacion():
    """R2: sin especificación → especificador; cuenta la vuelta."""
    destino, up = decidir({})
    assert destino == "especificador" and up["vueltas"] == 1
    assert up["bitacora"] == ["[supervisor] R2 → especificador"]


def test_r3_preguntas_abiertas():
    """R3: preguntas sin decisión vigente → aclarar; terminar/responder/continuar."""
    esp = copy.deepcopy(falso.ESPECIFICACION)
    esp["preguntas_abiertas"] = ["¿orden?"]
    assert decidir({"especificacion": esp})[0] == "aclarar"
    vieja = _decision("aclaracion", "continuar", {"otra": 1})
    assert decidir({"especificacion": esp, "decision_aclaracion": vieja})[0] == "aclarar"
    terminar = _decision("aclaracion", "terminar", esp)
    destino, up = decidir({"especificacion": esp, "decision_aclaracion": terminar})
    assert destino == "fin" and up["estado_final"] == "DETENIDA POR LA PERSONA"
    responder = _decision("aclaracion", "responder", esp, "de mayor a menor")
    assert decidir({"especificacion": esp, "decision_aclaracion": responder})[0] == "especificador"
    continuar = _decision("aclaracion", "continuar", esp)
    assert decidir({"especificacion": esp, "decision_aclaracion": continuar})[0] == "planificador"


def test_r4_sin_plan():
    """R4: sin plan → planificador."""
    assert decidir({"especificacion": falso.ESPECIFICACION})[0] == "planificador"


def test_r5_decision_no_vigente():
    """R5: sin decisión, o con una decisión sobre otro plan → aprobar_plan."""
    e = _base()
    del e["decision_plan"]
    assert decidir(e)[0] == "aprobar_plan"
    e["decision_plan"] = _decision("plan", "aprobar", {"plan": "anterior"})
    assert decidir(e)[0] == "aprobar_plan"


def test_r6_terminar():
    """R6: terminar → fin · DETENIDA POR LA PERSONA."""
    e = _base()
    e["decision_plan"] = _decision("plan", "terminar", e["plan"])
    destino, up = decidir(e)
    assert destino == "fin" and up["estado_final"] == "DETENIDA POR LA PERSONA"


@pytest.mark.parametrize("rechazos, esperado", [(1, "planificador"), (2, "planificador"),
                                                 (3, "fin")])
def test_r7_rechazo_con_tope(rechazos, esperado):
    """R7: el 1.º y 2.º rechazo replanifican; el 3.º escala."""
    e = _base()
    e["decision_plan"] = _decision("plan", "rechazar", e["plan"], "cubre el día 31")
    e["rechazos_plan"] = rechazos
    destino, up = decidir(e)
    assert destino == esperado
    if esperado == "fin":
        assert up["motivo_final"] == "el plan no converge"


def test_r8_abanico():
    """R8: sin implementación ni pruebas → implementador ∥ tester."""
    destino, up = decidir(_base())
    assert destino == ["implementador", "tester"]
    assert "implementador ∥ tester" in up["bitacora"][-1]


def test_r9_r10_falta_una():
    """R9/R10: falta una de las dos."""
    e = _base()
    e["pruebas"] = {"sha256": "p"}
    assert decidir(e)[0] == "implementador"
    e = _base()
    e["implementacion"] = {"sha256": "i"}
    assert decidir(e)[0] == "tester"


def test_r11_ejecucion_no_vigente():
    """R11: sin ejecución, o de otro par → sandbox."""
    e = _con_ejecucion(True)
    e["implementacion"]["sha256"] = "i2"
    assert decidir(e)[0] == "sandbox"


def test_r12_revision_no_vigente():
    """R12: la revisión es de otra ejecución → reviewer."""
    e = _con_ejecucion(True)
    e["revision"]["evaluado"] = "viejo"
    assert decidir(e)[0] == "reviewer"


def test_r13_corregir_al_responsable():
    """R13: corregir con ciclos < 2 → responsable, con la corrección y ciclos + 1."""
    e = _con_ejecucion(False, "corregir", "tester")
    destino, up = decidir(e)
    assert destino == "tester" and up["ciclos_correccion"] == 1
    assert up["correccion"]["responsable"] == "tester" and up["correccion"]["criterio"] == "C-01"
    assert up["correccion"]["fallos"] == ["test_cp02: assert"]


def test_r13_anula_aprobar_con_pruebas_fallidas():
    """El supervisor nunca aprueba con pruebas fallidas; responsable por omisión: implementador."""
    e = _con_ejecucion(False, "aprobar", None)
    destino, up = decidir(e)
    assert destino == "implementador"
    assert any("se anula" in linea for linea in up["bitacora"])
    assert "Las pruebas fallan" in up["correccion"]["instruccion"]


def test_r13_tope_y_escalamiento():
    """Con 2 ciclos → escalar; aceptar sigue a documentar; terminar → DETENIDA."""
    e = _con_ejecucion(False, "corregir", "implementador")
    e["ciclos_correccion"] = config.MAX_CICLOS
    assert decidir(e)[0] == "escalar"
    e["decision_escalamiento"] = _decision("escalamiento", "aceptar", e["revision"], "falta x")
    assert decidir(e)[0] == "documentador"
    e["documentacion"] = {"readme": "# x"}
    destino, up = decidir(e)
    assert destino == "fin" and up["estado_final"] == "LISTA CON OBSERVACIONES"
    assert up["motivo_final"] == "falta x"
    e = _con_ejecucion(False, "corregir", "implementador")
    e["ciclos_correccion"] = config.MAX_CICLOS
    e["decision_escalamiento"] = _decision("escalamiento", "terminar", e["revision"])
    destino, up = decidir(e)
    assert destino == "fin" and up["estado_final"] == "DETENIDA POR LA PERSONA"


def test_r13_escalamiento_de_otra_revision_no_vale():
    """Una decisión de escalamiento sobre otra revisión no está vigente."""
    e = _con_ejecucion(False, "corregir", "implementador")
    e["ciclos_correccion"] = config.MAX_CICLOS
    e["decision_escalamiento"] = _decision("escalamiento", "aceptar", {"otra": 1}, "x")
    assert decidir(e)[0] == "escalar"


def test_r14_documentador():
    """R14: aprobado y sin documentación → documentador."""
    assert decidir(_con_ejecucion(True))[0] == "documentador"


def test_r15_lista():
    """R15: todo listo → fin · LISTA."""
    e = _con_ejecucion(True)
    e["documentacion"] = {"readme": "# x"}
    destino, up = decidir(e)
    assert destino == "fin" and up["estado_final"] == "LISTA"


def test_es_pura():
    """decidir no modifica el estado que recibe."""
    e = _con_ejecucion(False, "corregir", "tester")
    copia = copy.deepcopy(e)
    decidir(e)
    assert e == copia


def test_nodo_devuelve_command():
    """El nodo envuelve la decisión en Command(update, goto)."""
    cmd = supervisor.nodo({})
    assert isinstance(cmd, Command) and cmd.goto == "especificador"
    assert cmd.update["vueltas"] == 1
