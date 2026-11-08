"""Paso 4: el envoltorio de claude -p (con subprocess.run simulado) y el modelo falso."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from fabrica import falso, modelo
from fabrica.config import RAIZ


class _Resultado:
    def __init__(self, stdout: str, returncode: int = 0, stderr: str = ""):
        self.stdout, self.returncode, self.stderr = stdout, returncode, stderr


@pytest.fixture
def capturar(monkeypatch):
    """Sustituye subprocess.run y guarda los argumentos de cada llamada."""
    llamadas = []
    salida = {"type": "result", "is_error": False, "num_turns": 2, "total_cost_usd": 0.0123,
              "usage": {"input_tokens": 10, "output_tokens": 5},
              "structured_output": {"motivo": "ok", "sospechosa": False}}

    def falso_run(cmd, **kw):
        llamadas.append({"cmd": cmd, **kw, "cwd_existe": Path(kw["cwd"]).is_dir()})
        return _Resultado(json.dumps(salida))

    monkeypatch.setattr(modelo.subprocess, "run", falso_run)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "no-debe-pasar")
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.delenv("FABRICA_MODELO", raising=False)
    monkeypatch.delenv("FABRICA_MODELO_FILTRO", raising=False)
    return llamadas, salida


def test_banderas_y_entorno(capturar):
    """Sin herramientas, sin MCP, con esquema, sin API key ni CLAUDECODE y con tope de gasto."""
    llamadas, _ = capturar
    r = modelo.llamar("especificador", "Eres…", "<historia_no_confiable>x</historia_no_confiable>",
                      {"type": "object"})
    cmd = llamadas[0]["cmd"]
    assert cmd[:3] == ["claude", "-p", "<historia_no_confiable>x</historia_no_confiable>"]
    assert cmd[cmd.index("--tools") + 1] == ""
    assert "--strict-mcp-config" in cmd and "--no-session-persistence" in cmd
    assert cmd[cmd.index("--output-format") + 1] == "json"
    assert json.loads(cmd[cmd.index("--json-schema") + 1]) == {"type": "object"}
    assert cmd[cmd.index("--system-prompt") + 1] == "Eres…"
    assert cmd[cmd.index("--max-budget-usd") + 1] == "0.50"
    env = llamadas[0]["env"]
    assert "ANTHROPIC_API_KEY" not in env and "CLAUDECODE" not in env
    assert llamadas[0]["stdin"] is subprocess.DEVNULL
    assert r.datos == {"motivo": "ok", "sospechosa": False}
    assert r.costo_usd == pytest.approx(0.0123) and r.turnos == 2
    assert r.tokens["input_tokens"] == 10


def test_cwd_temporal_distinto_de_la_raiz(capturar):
    """El agente corre en una carpeta temporal vacía, no en la raíz del repositorio."""
    llamadas, _ = capturar
    modelo.llamar("planificador", "s", "p", {})
    cwd = Path(llamadas[0]["cwd"])
    assert llamadas[0]["cwd_existe"]
    assert cwd.resolve() != RAIZ.resolve() and RAIZ.resolve() not in cwd.resolve().parents
    assert not cwd.exists()  # se borra al terminar


def test_modelos_por_omision_y_variable(capturar, monkeypatch):
    """sonnet por omisión, haiku para el filtro y FABRICA_MODELO lo cambia."""
    llamadas, _ = capturar
    modelo.llamar("especificador", "s", "p", {})
    modelo.llamar("filtro", "s", "p", {})
    monkeypatch.setenv("FABRICA_MODELO", "opus")
    modelo.llamar("reviewer", "s", "p", {})
    usados = [x["cmd"][x["cmd"].index("--model") + 1] for x in llamadas]
    assert usados == ["sonnet", "haiku", "opus"]


@pytest.mark.parametrize(
    "salida, codigo, mensaje",
    [
        ({"is_error": True, "result": "sin cuota"}, 0, "error"),
        ({"is_error": False, "result": "texto"}, 0, "structured_output"),
        ({}, 1, "falló"),
    ],
)
def test_errores_lanzan_error_modelo(monkeypatch, salida, codigo, mensaje):
    """is_error, la falta de structured_output o un código ≠ 0 lanzan ErrorModelo."""
    monkeypatch.setattr(modelo.subprocess, "run",
                        lambda cmd, **kw: _Resultado(json.dumps(salida), codigo, "stderr"))
    with pytest.raises(modelo.ErrorModelo, match=mensaje):
        modelo.llamar("tester", "s", "p", {})


def test_timeout_y_sin_binario(monkeypatch):
    """Un timeout o la falta del binario también son ErrorModelo."""
    def tarda(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 1)

    monkeypatch.setattr(modelo.subprocess, "run", tarda)
    with pytest.raises(modelo.ErrorModelo, match="tardó"):
        modelo.llamar("tester", "s", "p", {})

    def no_existe(cmd, **kw):
        raise FileNotFoundError

    monkeypatch.setattr(modelo.subprocess, "run", no_existe)
    with pytest.raises(modelo.ErrorModelo, match="PATH"):
        modelo.ModeloReal().llamar("tester", "s", "p", {})


def test_salida_que_no_es_json(monkeypatch):
    """Una salida que no es JSON es ErrorModelo."""
    monkeypatch.setattr(modelo.subprocess, "run", lambda cmd, **kw: _Resultado("hola"))
    with pytest.raises(modelo.ErrorModelo, match="JSON"):
        modelo.llamar("tester", "s", "p", {})


@pytest.mark.skipif(shutil.which("claude") is None, reason="no está el binario claude")
def test_banderas_claude():
    """Cada bandera del envoltorio existe en `claude --help` (no gasta cuota)."""
    ayuda = subprocess.run(["claude", "--help"], capture_output=True, text=True, timeout=60,
                           env=modelo._entorno(), stdin=subprocess.DEVNULL).stdout
    faltan = [b for b in modelo.BANDERAS if b not in ayuda]
    assert faltan == []


def test_falso_escenario_desconocido():
    """Un escenario desconocido es un error."""
    with pytest.raises(ValueError):
        falso.ModeloFalso("inventado")


def test_falso_sin_memoria_y_registra():
    """El falso decide por el prompt, no por llamadas anteriores, y registra cada llamada."""
    m = falso.ModeloFalso("correccion")
    primera = m.llamar("implementador", "s", "sin nada", {})
    segunda = m.llamar("implementador", "s", "<correccion>…</correccion>", {})
    otra = falso.ModeloFalso("correccion").llamar("implementador", "s", "<correccion>x", {})
    assert primera.datos["archivos"][0]["contenido"] == falso.CODIGO_CON_ERROR
    assert segunda.datos == otra.datos == falso.IMPLEMENTACION
    assert m.agentes_llamados() == ["implementador", "implementador"]
    assert primera.modelo == "falso:correccion"


def test_falso_reviewer_por_ejecucion():
    """El reviewer falso aprueba si el sandbox pasó y culpa según el escenario si no."""
    ok = '<ejecucion>{"ok": true}</ejecucion>'
    mal = '<ejecucion>{"ok": false}</ejecucion>'
    assert falso.ModeloFalso("feliz").llamar("reviewer", "", ok, {}).datos["veredicto"] == "aprobar"
    culpa = falso.ModeloFalso("tester_culpable").llamar("reviewer", "", mal, {}).datos
    assert culpa["responsable"] == "tester"
    impl = falso.ModeloFalso("correccion").llamar("reviewer", "", mal, {}).datos
    assert impl["responsable"] == "implementador"


def test_falso_agente_desconocido():
    """Un agente que el falso no conoce es ErrorModelo."""
    with pytest.raises(modelo.ErrorModelo):
        falso.ModeloFalso().llamar("nadie", "", "", {})
