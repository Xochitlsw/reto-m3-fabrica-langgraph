"""Envoltorio de ``claude -p``: llama al modelo con la suscripción de Claude Code, sin API key.

Parte de ``ejemplos/comun.py`` de M3B (``_comando``, ``_entorno``, ``claude``). Lo que cambia va
marcado como «adaptación, no viene del curso» (docs/diseno.md, sección 6).
"""

import json
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field

TIMEOUT = 300
MODELO_POR_OMISION = "sonnet"
MODELO_FILTRO_POR_OMISION = "haiku"
PRESUPUESTO_POR_OMISION = "0.50"
# Adaptación, no viene del curso: CLAUDECODE también se quita (claude -p lanzado desde Claude Code
# puede negarse a correr si lo hereda).
VARIABLES_QUITADAS = ("ANTHROPIC_API_KEY", "CLAUDECODE")
BANDERAS = (
    "-p",
    "--output-format",
    "--no-session-persistence",
    "--tools",
    "--strict-mcp-config",
    "--system-prompt",
    "--json-schema",
    "--model",
    "--max-budget-usd",
)


class ErrorModelo(RuntimeError):
    """La llamada falló: código ≠ 0, is_error, timeout o sin structured_output."""


@dataclass
class RespuestaModelo:
    """Lo que devuelve una llamada: los datos estructurados y lo que costó."""

    datos: dict
    costo_usd: float = 0.0
    turnos: int = 0
    tokens: dict = field(default_factory=dict)
    segundos: float = 0.0
    modelo: str = ""


def modelo_para(agente: str) -> str:
    """El filtro usa un modelo pequeño; los demás, sonnet por omisión (FABRICA_MODELO lo cambia)."""
    if agente == "filtro":
        return os.environ.get("FABRICA_MODELO_FILTRO", MODELO_FILTRO_POR_OMISION)
    return os.environ.get("FABRICA_MODELO", MODELO_POR_OMISION)


def _comando(prompt: str, sistema: str, esquema: dict, modelo: str) -> list[str]:
    """La línea de comandos de ``claude -p`` sin herramientas y con salida estructurada."""
    return [
        "claude", "-p", prompt,
        "--output-format", "json",
        "--no-session-persistence",
        "--tools", "",  # "" = sin herramientas: solo razona y responde
        # Adaptación, no viene del curso: la cuenta tiene conectores MCP y --tools "" solo quita
        # las herramientas integradas.
        "--strict-mcp-config",
        "--system-prompt", sistema,
        "--json-schema", json.dumps(esquema, ensure_ascii=False),
        # Adaptación, no viene del curso: modelo explícito y tope de gasto por llamada.
        "--model", modelo,
        "--max-budget-usd", os.environ.get("FABRICA_PRESUPUESTO_LLAMADA", PRESUPUESTO_POR_OMISION),
    ]


def _entorno() -> dict:
    """Sin ANTHROPIC_API_KEY a propósito: así Claude Code usa la suscripción (claude auth login)."""
    return {k: v for k, v in os.environ.items() if k not in VARIABLES_QUITADAS}


def llamar(
    agente: str, sistema: str, prompt: str, esquema: dict, modelo: str | None = None
) -> RespuestaModelo:
    """Una llamada al modelo real. Devuelve el ``structured_output`` y lo que costó.

    Adaptación, no viene del curso: ``cwd`` es una carpeta temporal vacía por llamada, para que el
    agente no cargue el ``CLAUDE.md`` de desarrollo del repositorio.
    """
    modelo = modelo or modelo_para(agente)
    inicio = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="fabrica-claude-") as carpeta:
        try:
            r = subprocess.run(
                _comando(prompt, sistema, esquema, modelo),
                cwd=carpeta, capture_output=True, text=True, env=_entorno(),
                stdin=subprocess.DEVNULL, timeout=TIMEOUT,
            )
        except subprocess.TimeoutExpired as e:
            raise ErrorModelo(f"claude -p tardó más de {TIMEOUT} s ({agente})") from e
        except FileNotFoundError as e:
            raise ErrorModelo("No se encontró el programa claude en el PATH") from e
    if r.returncode != 0:
        raise ErrorModelo(f"claude -p falló ({r.returncode}): {(r.stderr or r.stdout)[-500:]}")
    try:
        salida = json.loads(r.stdout)
    except ValueError as e:
        raise ErrorModelo(f"claude -p no devolvió JSON: {r.stdout[-300:]}") from e
    if salida.get("is_error"):
        raise ErrorModelo(f"claude -p devolvió un error: {str(salida.get('result'))[:300]}")
    datos = salida.get("structured_output")
    if not isinstance(datos, dict):
        raise ErrorModelo("claude -p no devolvió structured_output")
    return RespuestaModelo(
        datos=datos,
        costo_usd=float(salida.get("total_cost_usd") or 0.0),
        turnos=int(salida.get("num_turns") or 0),
        tokens=dict(salida.get("usage") or {}),
        segundos=round(time.monotonic() - inicio, 2),
        modelo=modelo,
    )


class ModeloReal:
    """Adaptador con la misma interfaz que ``ModeloFalso``."""

    def llamar(
        self, agente: str, sistema: str, prompt: str, esquema: dict, modelo: str | None = None
    ) -> RespuestaModelo:
        """Delegado a :func:`llamar`."""
        return llamar(agente, sistema, prompt, esquema, modelo)
