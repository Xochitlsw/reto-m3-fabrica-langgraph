"""Paso 11: checkpoints en SQLite entre procesos distintos y la CLI.

``iniciar`` se detiene en la pausa y termina; ``estado`` y ``aprobar`` son procesos nuevos que
retoman el mismo ``thread_id`` desde ``datos/checkpoints.sqlite`` (aquí, una base temporal).
"""

import subprocess
import sys

import pytest

from fabrica import cli, config

HU05 = "historias/HU-05-consultar-antiguedad.md"


def fabrica(*args: str, db) -> subprocess.CompletedProcess:
    """Corre ``python -m fabrica`` en un proceso nuevo (hereda las rutas temporales)."""
    return subprocess.run([sys.executable, "-m", "fabrica", *args, "--db", str(db)],
                          cwd=config.RAIZ, capture_output=True, text=True, timeout=120,
                          stdin=subprocess.DEVNULL)


def test_iniciar_estado_aprobar_en_procesos_distintos(rutas_temporales):
    """iniciar (3) → estado (next=aprobar_plan) → aprobar (0, LISTA) con el mismo thread_id."""
    db = rutas_temporales / "cp.sqlite"
    r = fabrica("iniciar", HU05, "--hilo", "HU-05-prueba", "--falso", "feliz", db=db)
    assert r.returncode == 3, r.stdout + r.stderr
    assert "⏸ PAUSA aprobar_plan · hilo HU-05-prueba" in r.stdout
    r = fabrica("estado", "HU-05-prueba", db=db)
    assert r.returncode == 3
    assert "next: ['aprobar_plan']" in r.stdout and "msgpack estricto: sí" in r.stdout
    r = fabrica("aprobar", "HU-05-prueba", "--operador", "xochitl", "--decision", "aprobar", db=db)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "■ LISTA" in r.stdout and "[sandbox] OK · 6 aprobadas" in r.stdout
    r = fabrica("estado", "HU-05-prueba", "--historial", db=db)
    assert r.returncode == 0 and "estado final: LISTA" in r.stdout and "historial" in r.stdout
    assert (rutas_temporales / "salida" / "HU-05-prueba" / "codigo" / "antiguedad.py").exists()


def test_otro_thread_id_empieza_de_cero(rutas_temporales):
    """Con otro thread_id no hay pausa que retomar, y iniciar empieza desde el principio."""
    db = rutas_temporales / "cp.sqlite"
    assert fabrica("iniciar", HU05, "--hilo", "uno", "--falso", "feliz", db=db).returncode == 3
    r = fabrica("aprobar", "otro", "--operador", "xochitl", "--decision", "aprobar", db=db)
    assert r.returncode == 2 and "no tiene una pausa pendiente" in r.stdout
    r = fabrica("estado", "otro", db=db)
    assert r.returncode == 2 and "no tiene checkpoints" in r.stdout
    r = fabrica("iniciar", HU05, "--hilo", "otro", "--falso", "feliz", db=db)
    assert r.returncode == 3 and "[guardian] OK" in r.stdout
    assert "vueltas: 3" in fabrica("estado", "otro", db=db).stdout


def test_rechazo_entre_procesos(rutas_temporales):
    """Rechazar en un proceso deja una pausa nueva; aprobar en otro termina LISTA."""
    db = rutas_temporales / "cp.sqlite"
    fabrica("iniciar", HU05, "--hilo", "r", "--falso", "feliz", db=db)
    r = fabrica("aprobar", "r", "--operador", "xochitl", "--decision", "rechazar",
                "--comentario", "Cubre el corte el mismo día", db=db)
    assert r.returncode == 3 and "rechazos 1 de 2" in r.stdout
    r = fabrica("aprobar", "r", "--operador", "xochitl", "--decision", "aprobar", db=db)
    assert r.returncode == 0 and "■ LISTA" in r.stdout


def test_operador_no_permitido_sigue_en_pausa(rutas_temporales):
    """Un operador fuera de la lista no reanuda y queda en el log."""
    db = rutas_temporales / "cp.sqlite"
    fabrica("iniciar", HU05, "--hilo", "o", "--falso", "feliz", db=db)
    r = fabrica("aprobar", "o", "--operador", "intruso", "--decision", "aprobar", db=db)
    assert r.returncode == 2 and "intruso" in r.stdout
    assert "next: ['aprobar_plan']" in fabrica("estado", "o", db=db).stdout
    log = (rutas_temporales / "logs" / "seguridad.jsonl").read_text(encoding="utf-8")
    assert '"respuesta_rechazada"' in log and '"intruso"' in log


# --- La CLI en el mismo proceso (para la cobertura y los casos de uso inválido) -----------------
def test_cli_en_proceso_flujo_y_errores(rutas_temporales, capsys):
    """Los mismos comandos llamando a main(); también los casos de uso inválido."""
    db = str(rutas_temporales / "cp.sqlite")
    assert cli.main(["iniciar", HU05, "--hilo", "p", "--falso", "escalar", "--db", db]) == 3
    assert cli.main(["iniciar", HU05, "--hilo", "p", "--falso", "feliz", "--db", db]) == 2
    assert cli.main(["aprobar", "p", "--operador", "xochitl", "--decision", "aprobar",
                     "--db", db]) == 3  # ahora la pausa es el escalamiento
    assert "PAUSA escalar" in capsys.readouterr().out
    assert cli.main(["aprobar", "p", "--operador", "xochitl", "--decision", "aceptar",
                     "--comentario", "Falta un caso", "--db", db]) == 0
    assert "LISTA CON OBSERVACIONES" in capsys.readouterr().out
    assert cli.main(["estado", "p", "--db", db]) == 0
    assert cli.main(["iniciar", HU05, "--falso", "inventado", "--db", db]) == 2
    assert cli.main(["iniciar", "historias/../secretos_demo.txt", "--hilo", "b", "--falso",
                     "feliz", "--db", db]) == 4
    assert cli.main(["comando-que-no-existe"]) == 2


def test_cli_real_pide_confirmacion(monkeypatch, rutas_temporales):
    """Sin confirmación, ni iniciar con el modelo real ni la sonda llaman al modelo."""
    def prohibido(*a, **k):
        raise AssertionError("no debía llamar a claude")

    monkeypatch.setattr("builtins.input", lambda _: "n")
    monkeypatch.setattr(subprocess, "run", prohibido)
    db = str(rutas_temporales / "cp.sqlite")
    assert cli.main(["iniciar", HU05, "--db", db]) == 2
    assert cli.main(["sonda"]) == 2

    def sin_terminal(_):
        raise EOFError

    monkeypatch.setattr("builtins.input", sin_terminal)
    assert cli.main(["sonda"]) == 2


def test_cli_grafo(rutas_temporales, capsys):
    """grafo escribe el Mermaid generado o lo imprime."""
    destino = rutas_temporales / "grafo.md"
    assert cli.main(["grafo", "--salida", str(destino)]) == 0
    texto = destino.read_text(encoding="utf-8")
    assert texto.startswith("# Grafo de la fábrica") and "```mermaid" in texto
    assert cli.main(["grafo"]) == 0 and "supervisor" in capsys.readouterr().out


def test_cli_error_inesperado(monkeypatch, capsys):
    """Un error inesperado sale con 1 y se reporta en stderr."""
    def falla(args):
        raise RuntimeError("se rompió")

    monkeypatch.setattr(cli, "cmd_grafo", falla)
    assert cli.main(["grafo"]) == 1
    assert "se rompió" in capsys.readouterr().err


@pytest.mark.parametrize("final, codigo", [("LISTA", 0), ("BLOQUEADA POR SEGURIDAD", 4),
                                           ("ESCALAR A UNA PERSONA", 5), ("raro", 1)])
def test_codigos_de_salida(final, codigo):
    """Los códigos de salida del diseño."""
    assert cli.SALIDA_POR_ESTADO.get(final, 1) == codigo
