"""La CLI: iniciar, aprobar, estado, grafo y sonda (docs/diseno.md, sección 7).

Cada invocación abre el checkpointer SQLite, compila el grafo y usa el ``thread_id`` del hilo.
``iniciar`` corre hasta la primera pausa y el proceso termina; ``aprobar`` (otro proceso) lee la
pausa pendiente con ``get_state`` y reanuda con ``Command(resume=...)`` y el mismo ``thread_id``.

Códigos de salida: 0 LISTA o LISTA CON OBSERVACIONES · 3 EN PAUSA · 4 BLOQUEADA · 5 DETENIDA o
ESCALAR · 2 uso inválido · 1 error.
"""

import argparse
import json
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from fabrica import config

SALIDA_POR_ESTADO = {
    "LISTA": 0,
    "LISTA CON OBSERVACIONES": 0,
    "BLOQUEADA POR SEGURIDAD": 4,
    "DETENIDA POR LA PERSONA": 5,
    "ESCALAR A UNA PERSONA": 5,
}
EN_PAUSA = 3
USO_INVALIDO = 2


@contextmanager
def abrir_grafo(db: Path):
    """El grafo compilado con un ``SqliteSaver`` sobre ``db``."""
    from langgraph.checkpoint.sqlite import SqliteSaver

    from fabrica.grafo import construir_grafo

    db.parent.mkdir(parents=True, exist_ok=True)
    with SqliteSaver.from_conn_string(str(db)) as checkpointer:
        yield construir_grafo(checkpointer)


def _cfg(hilo: str) -> dict:
    return {"configurable": {"thread_id": hilo}}


def pausa_pendiente(snapshot) -> dict | None:
    """El paquete de la pausa pendiente del hilo, si la hay (``StateSnapshot.tasks[*]``)."""
    for tarea in snapshot.tasks:
        for interrupcion in tarea.interrupts:
            return interrupcion.value
    return None


def _confirmar(mensaje: str, si: bool) -> bool:
    """Pide confirmación antes de gastar cuota de la suscripción."""
    if si:
        return True
    print(mensaje)
    try:
        return input("¿Continuar? [s/N] ").strip().lower() in ("s", "si", "sí")
    except EOFError:
        return False


def _correr(app, entrada, hilo: str) -> int:
    """Corre con ``stream(stream_mode="updates")`` imprimiendo la bitácora; reporta el final."""
    for evento in app.stream(entrada, _cfg(hilo), stream_mode="updates"):
        for nodo, update in evento.items():
            if nodo == "__interrupt__" or not isinstance(update, dict):
                continue
            for linea in update.get("bitacora", []):
                if not linea.startswith("[supervisor]"):
                    print(f"  {linea}")
    return _reportar(app, hilo)


def _reportar(app, hilo: str) -> int:
    """Imprime la pausa pendiente o el estado final y devuelve el código de salida."""
    snapshot = app.get_state(_cfg(hilo))
    paquete = pausa_pendiente(snapshot)
    if paquete:
        contadores = " · ".join(f"{k} {v}" for k, v in paquete.get("contadores", {}).items()
                                if k != "max")
        tope = paquete.get("contadores", {}).get("max")
        print(f"\n⏸ PAUSA {snapshot.next[0]} · hilo {hilo} · {contadores}"
              + (f" de {tope}" if tope is not None else ""))
        print(f"\n## {paquete['titulo']}\n\n{paquete['resumen']}\n")
        print(f"sha256: {paquete['sha256']}")
        for problema in paquete.get("problemas", []):
            print(f"  ✗ {problema}")
        comentario = " [--comentario \"…\"]"
        print(f"Para seguir: python -m fabrica aprobar {hilo} --operador <id> "
              f"--decision {'|'.join(paquete['opciones'])}{comentario}")
        return EN_PAUSA
    valores = snapshot.values
    final = valores.get("estado_final", "")
    print(f"\n■ {final} · {valores.get('motivo_final', '')}")
    print(f"  salida: {config.ruta_salida() / hilo}")
    print(f"  llamadas: {len(valores.get('llamadas', []))} · "
          f"costo: {valores.get('costo_usd', 0.0):.4f} USD")
    return SALIDA_POR_ESTADO.get(final, 1)


def cmd_iniciar(args) -> int:
    """Empieza una corrida nueva y corre hasta la primera pausa o el final."""
    ruta = Path(args.historia)
    hu = ruta.name[:5] if ruta.name.startswith("HU-") else "HU"
    hilo = args.hilo or f"{hu}-{datetime.now():%Y%m%d-%H%M%S}"
    modelo = f"falso:{args.falso}" if args.falso else "real"
    if args.falso:
        from fabrica.falso import ESCENARIOS

        if args.falso not in ESCENARIOS:
            print(f"Escenario desconocido: {args.falso}. Opciones: {', '.join(ESCENARIOS)}")
            return USO_INVALIDO
    elif not _confirmar("Esta corrida usa el modelo real y gasta cuota de la suscripción.",
                        args.si):
        print("Cancelado: no se llamó al modelo.")
        return USO_INVALIDO
    with abrir_grafo(Path(args.db)) as app:
        if app.get_state(_cfg(hilo)).values:
            print(f"El hilo {hilo} ya existe: usa «estado» o «aprobar», o elige otro --hilo.")
            return USO_INVALIDO
        print(f"▶ hilo {hilo} · modelo {modelo}")
        entrada = {"hilo": hilo, "historia_ruta": args.historia, "modelo": modelo}
        return _correr(app, entrada, hilo)


def cmd_aprobar(args) -> int:
    """Responde la pausa pendiente del hilo y reanuda en este proceso."""
    from langgraph.types import Command

    from fabrica.humano import problemas_de_respuesta
    from fabrica.seguridad import log

    with abrir_grafo(Path(args.db)) as app:
        snapshot = app.get_state(_cfg(args.hilo))
        paquete = pausa_pendiente(snapshot)
        if not paquete:
            print(f"El hilo {args.hilo} no tiene una pausa pendiente.")
            return USO_INVALIDO
        respuesta = {"pausa": paquete["pausa"], "decision": args.decision,
                     "comentario": args.comentario or "", "operador": args.operador,
                     "sobre_sha256": paquete["sha256"]}
        _, problemas = problemas_de_respuesta(respuesta, paquete["pausa"], paquete["sha256"],
                                              paquete["opciones"])
        if problemas:
            log.registrar("respuesta_rechazada", hilo=args.hilo, hu=paquete.get("hu", ""),
                          capa="hitl", nodo="cli", detalle=" | ".join(problemas),
                          operador=args.operador, usuario_so=log.usuario_so())
            for problema in problemas:
                print(f"  ✗ {problema}")
            print("La pausa sigue pendiente.")
            return USO_INVALIDO
        print(f"▶ hilo {args.hilo} · {paquete['pausa']} · {args.decision} · {args.operador}")
        return _correr(app, Command(resume=respuesta), args.hilo)


def cmd_estado(args) -> int:
    """Muestra el siguiente nodo, la pausa pendiente, los contadores y el costo del hilo."""
    from langgraph.checkpoint.serde import _msgpack

    with abrir_grafo(Path(args.db)) as app:
        snapshot = app.get_state(_cfg(args.hilo))
        valores = snapshot.values
        if not valores:
            print(f"El hilo {args.hilo} no tiene checkpoints.")
            return USO_INVALIDO
        paquete = pausa_pendiente(snapshot)
        print(f"hilo: {args.hilo}")
        print(f"next: {list(snapshot.next)}")
        print(f"pausa pendiente: {paquete['pausa'] if paquete else '—'}")
        print(f"estado final: {valores.get('estado_final', '—')}")
        print(f"vueltas: {valores.get('vueltas', 0)} · rechazos: {valores.get('rechazos_plan', 0)}"
              f" · ciclos: {valores.get('ciclos_correccion', 0)}")
        print(f"llamadas: {len(valores.get('llamadas', []))} · "
              f"costo: {valores.get('costo_usd', 0.0):.4f} USD")
        print(f"modelo: {valores.get('modelo', '')}")
        print(f"msgpack estricto: {'sí' if _msgpack.STRICT_MSGPACK_ENABLED else 'no'}")
        if args.historial:
            print("\nhistorial (del más reciente al más viejo):")
            for paso in app.get_state_history(_cfg(args.hilo)):
                print(f"  paso {paso.metadata.get('step')}: next={list(paso.next)}")
        return EN_PAUSA if paquete else SALIDA_POR_ESTADO.get(valores.get("estado_final"), 1)


def cmd_grafo(args) -> int:
    """Dibuja el grafo real con ``draw_mermaid`` (sin modelo)."""
    from fabrica.grafo import dibujar

    texto = dibujar()
    if args.salida:
        destino = Path(args.salida)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(
            "# Grafo de la fábrica (generado)\n\n"
            "Generado con `uv run python -m fabrica grafo --salida docs/grafo.md` "
            "(`app.get_graph().draw_mermaid()`). No se edita a mano.\n\n"
            f"```mermaid\n{texto.strip()}\n```\n", encoding="utf-8")
        print(f"Escrito {destino}")
    else:
        print(texto)
    return 0


def cmd_sonda(args) -> int:
    """Una llamada real barata para verificar el envoltorio (docs/diseno.md, sección 6)."""
    import subprocess
    import tempfile

    from fabrica.modelo import _entorno

    if not _confirmar("La sonda hace 1 llamada real con haiku (tope 0.05 USD).", args.si):
        print("Cancelado: no se llamó al modelo.")
        return USO_INVALIDO
    cmd = ["claude", "-p", "Responde solo: ok", "--model", "haiku", "--system-prompt",
           "Responde solo: ok", "--tools", "", "--strict-mcp-config", "--no-session-persistence",
           "--output-format", "stream-json", "--verbose", "--max-budget-usd", "0.05"]
    with tempfile.TemporaryDirectory(prefix="fabrica-sonda-") as carpeta:
        r = subprocess.run(cmd, cwd=carpeta, capture_output=True, text=True, env=_entorno(),
                           stdin=subprocess.DEVNULL, timeout=300)
    eventos = [json.loads(x) for x in r.stdout.splitlines() if x.strip().startswith("{")]
    inicio = next((e for e in eventos if e.get("type") == "system"), {})
    final = next((e for e in eventos if e.get("type") == "result"), {})
    uso = final.get("usage", {})
    entrada = sum(uso.get(k, 0) for k in ("input_tokens", "cache_creation_input_tokens",
                                          "cache_read_input_tokens"))
    print(f"tools: {inicio.get('tools')} · mcp_servers: {inicio.get('mcp_servers')}")
    print(f"tokens de entrada: {entrada} · turnos: {final.get('num_turns')} · "
          f"costo: {final.get('total_cost_usd')} USD · resultado: {final.get('result')!r}")
    ok = r.returncode == 0 and inicio.get("tools") == [] and inicio.get("mcp_servers") == []
    return 0 if ok else 1


def parser() -> argparse.ArgumentParser:
    """El parser de argumentos."""
    p = argparse.ArgumentParser(prog="fabrica", description="Fábrica de software multiagente.")
    sub = p.add_subparsers(dest="comando", required=True)
    db = {"default": str(config.ruta_db()), "help": "base SQLite de checkpoints"}

    q = sub.add_parser("iniciar", help="empieza una corrida")
    q.add_argument("historia")
    q.add_argument("--hilo")
    q.add_argument("--falso", metavar="ESCENARIO", help="usa el modelo falso (sin gasto)")
    q.add_argument("--si", action="store_true", help="no pedir confirmación del gasto")
    q.add_argument("--db", **db)
    q.set_defaults(func=cmd_iniciar)

    q = sub.add_parser("aprobar", help="responde la pausa pendiente y reanuda")
    q.add_argument("hilo")
    q.add_argument("--operador", required=True)
    q.add_argument("--decision", required=True,
                   choices=["aprobar", "rechazar", "continuar", "responder", "aceptar", "terminar"])
    q.add_argument("--comentario", default="")
    q.add_argument("--db", **db)
    q.set_defaults(func=cmd_aprobar)

    q = sub.add_parser("estado", help="muestra el estado del hilo (get_state)")
    q.add_argument("hilo")
    q.add_argument("--historial", action="store_true")
    q.add_argument("--db", **db)
    q.set_defaults(func=cmd_estado)

    q = sub.add_parser("grafo", help="dibuja el grafo (draw_mermaid)")
    q.add_argument("--salida")
    q.set_defaults(func=cmd_grafo)

    q = sub.add_parser("sonda", help="1 llamada real barata para verificar el envoltorio")
    q.add_argument("--si", action="store_true")
    q.set_defaults(func=cmd_sonda)
    return p


def main(argv: list[str] | None = None) -> int:
    """Ejecuta la CLI y devuelve el código de salida."""
    try:
        args = parser().parse_args(argv)
    except SystemExit as e:
        return USO_INVALIDO if e.code else 0
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 1
    except Exception as e:  # noqa: BLE001 - la CLI reporta el error y sale con 1
        print(f"Error: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
