"""El grafo de LangGraph: nodos, aristas y el nodo ``fin`` (docs/diseno.md, sección 1).

``guardian`` y ``filtro`` usan aristas condicionales con ``Literal``, como en el curso. El resto
sigue la topología de supervisor: cada nodo vuelve al supervisor con ``add_edge`` y el supervisor
devuelve ``Command(goto=...)``; la primera vez lanza implementador ∥ tester en paralelo.
"""

import json
import shutil
from pathlib import Path
from typing import Literal

from langgraph.graph import END, START, StateGraph

from fabrica import config, humano, supervisor
from fabrica.agentes import AGENTES
from fabrica.agentes.base import Modelo, como_nodo
from fabrica.estado import EstadoFabrica
from fabrica.seguridad import guardian, log, sandbox

AGENTES_DEL_SUPERVISOR = ("especificador", "planificador", "implementador", "tester", "reviewer",
                          "documentador")
REDACTADO = "[REDACTADO: bandera del señuelo]"


def despues_guardian(estado: EstadoFabrica) -> Literal["filtro", "fin"]:
    """Bloqueada → fin; si pasa → filtro."""
    return "fin" if (estado.get("seguridad") or {}).get("bloqueada") else "filtro"


def despues_filtro(estado: EstadoFabrica) -> Literal["supervisor", "fin"]:
    """Sospechosa → fin; si no → supervisor."""
    return "fin" if (estado.get("seguridad") or {}).get("bloqueada") else "supervisor"


def nodo_filtro(modelo: Modelo | None):
    """El filtro con modelo, salvo con DEFENSAS=0 (demo del ataque)."""
    agente = como_nodo(AGENTES["filtro"], modelo)

    def filtro(estado: EstadoFabrica) -> dict:
        if not estado.get("defensas", True):
            return {"bitacora": ["[filtro] apagado (DEFENSAS=0)"]}
        return agente(estado)

    return filtro


def _escribir(ruta: Path, texto: str) -> None:
    """Escribe un archivo; la bandera del señuelo nunca sale de la fábrica."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(texto.replace(config.BANDERA, REDACTADO), encoding="utf-8")


def reporte(estado: EstadoFabrica, final: str, motivo: str) -> str:
    """El reporte de la corrida en markdown, con la bitácora completa."""
    llamadas = estado.get("llamadas", [])
    lineas = [
        f"# Reporte · {estado.get('hu', '')} · hilo {estado.get('hilo', '')}",
        "",
        f"- **Estado final:** {final}",
        f"- **Motivo:** {motivo}",
        f"- **Modelo:** {estado.get('modelo', '')}",
        f"- **Ciclos de corrección:** {estado.get('ciclos_correccion', 0)} de {config.MAX_CICLOS}",
        f"- **Rechazos del plan:** {estado.get('rechazos_plan', 0)} de {config.MAX_RECHAZOS}",
        f"- **Vueltas del supervisor:** {estado.get('vueltas', 0)}",
        f"- **Llamadas al modelo:** {len(llamadas)}",
        f"- **Costo total:** {estado.get('costo_usd', 0.0):.4f} USD",
        "",
        "## Bitácora",
        "",
    ] + [f"{i}. {linea}" for i, linea in enumerate(estado.get("bitacora", []), 1)]
    return "\n".join(lineas) + "\n"


def escribir_salida(estado: EstadoFabrica, final: str, motivo: str) -> Path:
    """Escribe en ``salida/<hilo>/`` el reporte, las llamadas, lo generado y el log del hilo."""
    hilo = estado.get("hilo") or "sin-hilo"
    carpeta = config.ruta_salida() / hilo
    _escribir(carpeta / "reporte.md", reporte(estado, final, motivo))
    _escribir(carpeta / "llamadas.json",
              json.dumps(estado.get("llamadas", []), ensure_ascii=False, indent=2))
    for campo in ("especificacion", "plan", "revision", "ejecucion"):
        if estado.get(campo):
            _escribir(carpeta / f"{campo}.json",
                      json.dumps(estado[campo], ensure_ascii=False, indent=2))
    for campo, sub in (("implementacion", "codigo"), ("pruebas", "pruebas")):
        for archivo in (estado.get(campo) or {}).get("archivos", []):
            _escribir(carpeta / sub / archivo["nombre"], archivo["contenido"])
    if estado.get("documentacion"):
        _escribir(carpeta / "README.md", estado["documentacion"]["readme"])
    lineas = [json.dumps(x, ensure_ascii=False) for x in log.leer(hilo)]
    _escribir(carpeta / "seguridad.jsonl", "\n".join(lineas) + ("\n" if lineas else ""))
    return carpeta


def copiar_evidencia(carpeta: Path, hilo: str) -> Path:
    """Ajuste B: en una corrida real, copia lo generado a ``evidencia/corridas/<hilo>/``."""
    destino = config.ruta_evidencia() / hilo
    destino.mkdir(parents=True, exist_ok=True)
    for nombre in ("reporte.md", "llamadas.json", "README.md", "seguridad.jsonl"):
        if (carpeta / nombre).exists():
            shutil.copy2(carpeta / nombre, destino / nombre)
    for sub in ("codigo", "pruebas"):
        if (carpeta / sub).is_dir():
            shutil.copytree(carpeta / sub, destino / sub, dirs_exist_ok=True)
    return destino


def nodo_fin(estado: EstadoFabrica) -> dict:
    """Nodo ``fin``: fija el estado final, escribe la salida y, si es real, la evidencia."""
    final = estado.get("estado_final")
    motivo = estado.get("motivo_final", "")
    update: dict = {}
    if not final:  # llegó desde guardian o filtro: bloqueada por seguridad
        seguridad = estado.get("seguridad") or {}
        final = "BLOQUEADA POR SEGURIDAD"
        motivo = f"capa {seguridad.get('capa', '?')}: " + " | ".join(seguridad.get("motivos", []))
        update = {"estado_final": final, "motivo_final": motivo}
    carpeta = escribir_salida(estado, final, motivo)
    lineas = [f"[fin] {final} · {motivo}"[:300]]
    if estado.get("modelo") == "real":
        destino = copiar_evidencia(carpeta, estado.get("hilo") or "sin-hilo")
        lineas.append(f"[fin] evidencia copiada a {destino}")
    return {**update, "bitacora": lineas}


def construir_grafo(checkpointer=None, modelo: Modelo | None = None):
    """Compila el grafo. ``modelo`` permite inyectar un ``ModeloFalso`` en las pruebas."""
    g = StateGraph(EstadoFabrica)
    g.add_node("guardian", guardian.nodo)
    g.add_node("filtro", nodo_filtro(modelo))
    g.add_node("supervisor", supervisor.nodo)
    for nombre in AGENTES_DEL_SUPERVISOR:
        g.add_node(nombre, como_nodo(AGENTES[nombre], modelo))
    g.add_node("aclarar", humano.nodo_aclarar)
    g.add_node("aprobar_plan", humano.nodo_aprobar_plan)
    g.add_node("escalar", humano.nodo_escalar)
    g.add_node("sandbox", sandbox.nodo)
    g.add_node("fin", nodo_fin)

    g.add_edge(START, "guardian")
    g.add_conditional_edges("guardian", despues_guardian)
    g.add_conditional_edges("filtro", despues_filtro)
    for nombre in (*AGENTES_DEL_SUPERVISOR, "aclarar", "aprobar_plan", "escalar", "sandbox"):
        g.add_edge(nombre, "supervisor")
    g.add_edge("fin", END)
    return g.compile(checkpointer=checkpointer)


def dibujar() -> str:
    """El diagrama Mermaid del grafo real (``draw_mermaid``, sin modelo)."""
    return construir_grafo().get_graph().draw_mermaid()
