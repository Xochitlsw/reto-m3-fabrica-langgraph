"""Paso 10: el grafo punta a punta con el modelo falso e InMemorySaver."""

import re

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from fabrica import config, falso
from fabrica.grafo import construir_grafo, dibujar
from fabrica.seguridad import log

HU05 = str(config.RAIZ / "historias" / "HU-05-consultar-antiguedad.md")
HU99 = str(config.RAIZ / "historias" / "HU-99-exportar-antiguedad.md")


def aprobar_todo(paquete: dict) -> dict:
    """Política por omisión: continuar, aprobar y aceptar."""
    decision = {"aclaracion": "continuar", "plan": "aprobar", "escalamiento": "aceptar"}
    return {"decision": decision[paquete["pausa"]], "comentario": "visto por la persona"}


def correr(escenario: str, politica=aprobar_todo, ruta: str = HU05, hilo: str = "h"):
    """Corre el grafo resolviendo cada pausa con la política. Devuelve (estado, pausas, modelo)."""
    modelo = falso.ModeloFalso(escenario)
    app = construir_grafo(InMemorySaver(), modelo)
    cfg = {"configurable": {"thread_id": hilo}}
    salida = app.invoke({"hilo": hilo, "historia_ruta": ruta, "modelo": f"falso:{escenario}"}, cfg)
    pausas = []
    while "__interrupt__" in salida:
        paquete = salida["__interrupt__"][0].value
        pausas.append(paquete)
        respuesta = {"pausa": paquete["pausa"], "operador": "xochitl",
                     "sobre_sha256": paquete["sha256"], **politica(paquete)}
        salida = app.invoke(Command(resume=respuesta), cfg)
        assert len(pausas) < 10
    return salida, pausas, modelo


def nodos(estado: dict) -> list[str]:
    """Los nodos (sin el supervisor) en el orden de la bitácora."""
    return [re.match(r"\[(\w+)\]", x).group(1) for x in estado["bitacora"]
            if not x.startswith("[supervisor]")]


def test_feliz():
    """Orden spec → plan → aprobación → implementador ∥ tester → sandbox → revisión → docs."""
    estado, pausas, modelo = correr("feliz")
    assert estado["estado_final"] == "LISTA"
    assert [p["pausa"] for p in pausas] == ["plan"]
    orden = nodos(estado)
    assert orden[:4] == ["guardian", "filtro", "especificador", "planificador"]
    assert orden[4] == "aprobar_plan" and set(orden[5:7]) == {"implementador", "tester"}
    assert orden[7:] == ["sandbox", "reviewer", "documentador", "fin"]
    assert modelo.agentes_llamados().count("implementador") == 1
    assert "[supervisor] R8 · abanico → implementador ∥ tester" in estado["bitacora"]
    assert estado["ejecucion"]["aprobadas"] == 6


def test_feliz_escribe_la_salida(rutas_temporales):
    """fin escribe reporte, código, pruebas, README y el log del hilo; sin evidencia (falso)."""
    correr("feliz", hilo="hilo-salida")
    carpeta = rutas_temporales / "salida" / "hilo-salida"
    assert "LISTA" in (carpeta / "reporte.md").read_text(encoding="utf-8")
    assert (carpeta / "codigo" / "antiguedad.py").exists()
    assert (carpeta / "pruebas" / "test_antiguedad.py").exists()
    assert (carpeta / "README.md").exists() and (carpeta / "seguridad.jsonl").exists()
    assert not (rutas_temporales / "evidencia").exists()


def test_preguntas_responder():
    """Preguntas abiertas → aclarar → responder → especificador de nuevo, sin preguntas."""
    def politica(p):
        if p["pausa"] == "aclaracion":
            return {"decision": "responder", "comentario": "De mayor a menor antigüedad"}
        return aprobar_todo(p)

    estado, pausas, modelo = correr("preguntas", politica)
    assert estado["estado_final"] == "LISTA"
    assert [p["pausa"] for p in pausas] == ["aclaracion", "plan"]
    assert modelo.agentes_llamados().count("especificador") == 2
    assert estado["aclaraciones"] == 1


def test_preguntas_continuar_y_terminar():
    """Continuar sigue con las preguntas; terminar detiene."""
    estado, _, _ = correr("preguntas")
    assert estado["estado_final"] == "LISTA"
    estado, _, modelo = correr("preguntas", lambda p: {"decision": "terminar"})
    assert estado["estado_final"] == "DETENIDA POR LA PERSONA"
    assert "planificador" not in modelo.agentes_llamados()


def test_rechazo_replanifica_con_el_comentario():
    """Un rechazo vuelve al planificador con el comentario; el nuevo plan se aprueba."""
    def politica(p):
        if p["pausa"] == "plan" and p["contadores"]["rechazos"] == 0:
            return {"decision": "rechazar", "comentario": "Cubre el corte el mismo día"}
        return aprobar_todo(p)

    estado, pausas, modelo = correr("feliz", politica)
    assert estado["estado_final"] == "LISTA" and estado["rechazos_plan"] == 1
    assert len(pausas) == 2 and pausas[0]["sha256"] != pausas[1]["sha256"]
    assert "<comentario_operador>" in modelo.llamadas[3]["prompt"]


def test_tres_rechazos_escalan():
    """Al tercer rechazo, ESCALAR («el plan no converge»)."""
    estado, pausas, _ = correr("feliz", lambda p: {"decision": "rechazar", "comentario": "no"})
    assert estado["estado_final"] == "ESCALAR A UNA PERSONA"
    assert estado["motivo_final"] == "el plan no converge" and len(pausas) == 3
    assert "ESCALAR" in pausas[-1]["resumen"]


def test_plan_terminar():
    """Terminar en el plan detiene sin implementar."""
    estado, _, modelo = correr("feliz", lambda p: {"decision": "terminar"})
    assert estado["estado_final"] == "DETENIDA POR LA PERSONA"
    assert "implementador" not in modelo.agentes_llamados()


def test_correccion_del_implementador():
    """El código falla, el reviewer culpa al implementador y una corrección lo arregla."""
    estado, _, modelo = correr("correccion")
    assert estado["estado_final"] == "LISTA" and estado["ciclos_correccion"] == 1
    assert estado["correccion"]["responsable"] == "implementador"
    assert modelo.agentes_llamados().count("implementador") == 2
    assert modelo.agentes_llamados().count("tester") == 1
    assert nodos(estado).count("sandbox") == 2


def test_tester_culpable():
    """La prueba contradice C-03: el triage manda la corrección al tester."""
    estado, _, modelo = correr("tester_culpable")
    assert estado["estado_final"] == "LISTA" and estado["correccion"]["responsable"] == "tester"
    assert modelo.agentes_llamados().count("tester") == 2
    assert modelo.agentes_llamados().count("implementador") == 1


def test_escalar_aceptar():
    """Dos ciclos sin arreglo → escalar → aceptar → documentador → LISTA CON OBSERVACIONES."""
    estado, pausas, modelo = correr("escalar")
    assert [p["pausa"] for p in pausas] == ["plan", "escalamiento"]
    assert estado["estado_final"] == "LISTA CON OBSERVACIONES"
    assert estado["ciclos_correccion"] == 2 and modelo.agentes_llamados()[-1] == "documentador"
    assert "<observaciones_operador>" in modelo.llamadas[-1]["prompt"]
    assert [x["evento"] for x in log.leer("h")][-1] == "escalamiento"


def test_escalar_terminar():
    """Al escalar, terminar detiene sin documentar."""
    def politica(p):
        return {"decision": "terminar"} if p["pausa"] == "escalamiento" else aprobar_todo(p)

    estado, _, modelo = correr("escalar", politica)
    assert estado["estado_final"] == "DETENIDA POR LA PERSONA"
    assert "documentador" not in modelo.agentes_llamados()


def test_contrato_invalido_escala():
    """Dos salidas inválidas del planificador → ESCALAR sin pausa humana."""
    estado, pausas, modelo = correr("contrato_invalido")
    assert estado["estado_final"] == "ESCALAR A UNA PERSONA" and pausas == []
    assert "planificador" in estado["motivo_final"]
    assert modelo.agentes_llamados().count("planificador") == 2


def test_sospechosa_bloquea_sin_mas_llamadas():
    """El filtro marca la historia: BLOQUEADA y 0 llamadas después del filtro."""
    estado, _, modelo = correr("sospechosa")
    assert estado["estado_final"] == "BLOQUEADA POR SEGURIDAD"
    assert modelo.agentes_llamados() == ["filtro"]


def test_guardian_bloquea_la_ruta_sin_llamar_al_modelo():
    """Una ruta fuera de historias/ se bloquea en la capa 1: 0 llamadas al modelo."""
    estado, _, modelo = correr("feliz", ruta="historias/../secretos_demo.txt")
    assert estado["estado_final"] == "BLOQUEADA POR SEGURIDAD"
    assert modelo.agentes_llamados() == [] and estado["historia_texto"] == ""
    assert log.leer("h")[0]["evento"] == "bloqueo"


def test_ataque_lo_detiene_la_lista_blanca():
    """El implementador del escenario ataque no pasa la revisión estática → ESCALAR."""
    estado, _, _ = correr("ataque")
    assert estado["estado_final"] == "ESCALAR A UNA PERSONA"
    assert "implementador" in estado["motivo_final"]


# --- Fase 3: la demo del ataque con HU-99 ------------------------------------------------------
def test_demo_hu99_con_defensas_bloquea_sin_llamar_al_modelo():
    """Con defensas, la capa 1 bloquea HU-99 por su contenido: BLOQUEADA y 0 llamadas al modelo."""
    estado, _, modelo = correr("feliz", ruta=HU99, hilo="d1")
    assert estado["estado_final"] == "BLOQUEADA POR SEGURIDAD"
    assert modelo.agentes_llamados() == []
    assert log.leer("d1")[0]["evento"] == "bloqueo"


def test_demo_hu99_sin_defensas_la_detiene_la_revision_estatica(monkeypatch, rutas_temporales):
    """Con DEFENSAS=0, HU-99 llega a los agentes; la revisión estática del código → ESCALAR."""
    monkeypatch.setenv("DEFENSAS", "0")
    estado, _, modelo = correr("ataque", ruta=HU99, hilo="d2")
    assert estado["estado_final"] == "ESCALAR A UNA PERSONA"
    assert "implementador" in estado["motivo_final"]
    assert "implementador" in modelo.agentes_llamados()  # las defensas estaban apagadas
    eventos = {x["evento"] for x in log.leer("d2")}
    assert "defensas_desactivadas" in eventos and "salida_rechazada" in eventos
    salida = rutas_temporales / "salida" / "d2"
    for archivo in salida.rglob("*"):
        if archivo.is_file():
            assert config.BANDERA not in archivo.read_text(encoding="utf-8")


def test_dibujo_con_las_aristas():
    """El dibujo trae los 14 nodos y las aristas principales."""
    texto = dibujar()
    for nodo in ("guardian", "filtro", "supervisor", "especificador", "aclarar", "planificador",
                 "aprobar_plan", "implementador", "tester", "sandbox", "reviewer", "escalar",
                 "documentador", "fin"):
        assert nodo in texto
    assert "__start__ --> guardian" in texto and "fin --> __end__" in texto
    assert "implementador --> supervisor" in texto


@pytest.mark.parametrize("escenario", ["feliz", "correccion", "tester_culpable"])
def test_nunca_aprueba_con_pruebas_fallidas(escenario):
    """Si termina LISTA, la última ejecución pasó."""
    estado, _, _ = correr(escenario)
    assert estado["ejecucion"]["ok"] and estado["ejecucion"]["fallidas"] == 0
