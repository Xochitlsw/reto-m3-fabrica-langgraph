"""La pieza común de los agentes: prompt endurecido, contrato, validador y reintento con tope.

Cada agente define su contrato, cómo arma el turno de usuario (los datos entre delimitadores, como
datos y no como instrucciones), cómo se valida su salida y qué campo del estado escribe. La llamada
reintenta una vez con los problemas del validador; al segundo fallo deja un ``errores_agente`` y el
supervisor escala a una persona (docs/diseno.md, sección 1.4).
"""

import json
from collections.abc import Callable
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError

from fabrica import config
from fabrica.contratos import problemas_pydantic
from fabrica.estado import EstadoFabrica
from fabrica.modelo import ErrorModelo, ModeloReal, RespuestaModelo
from fabrica.seguridad import log


class Modelo(Protocol):
    """Lo que necesita un agente de un modelo: ``ModeloReal`` o ``ModeloFalso``."""

    def llamar(
        self, agente: str, sistema: str, prompt: str, esquema: dict, modelo: str | None = None
    ) -> RespuestaModelo:
        """Una llamada con salida estructurada."""
        ...


def cargar_prompt(agente: str) -> str:
    """El prompt de sistema del agente (``fabrica/prompts/<agente>.md``)."""
    return (config.PROMPTS / f"{agente}.md").read_text(encoding="utf-8")


def envolver(etiqueta: str, contenido: Any) -> str:
    """Pone los datos entre delimitadores; neutraliza un cierre falso dentro del contenido."""
    if not isinstance(contenido, str):
        contenido = json.dumps(contenido, ensure_ascii=False, indent=2)
    contenido = contenido.replace(f"</{etiqueta}>", f"&lt;/{etiqueta}&gt;")
    return f"<{etiqueta}>\n{contenido}\n</{etiqueta}>"


def resolver_modelo(estado: EstadoFabrica, inyectado: Modelo | None) -> Modelo:
    """El modelo de esta corrida. Una corrida empezada con el falso nunca llama al real."""
    from fabrica.falso import ModeloFalso  # import diferido: falso importa de modelo

    marca = estado.get("modelo") or "falso:feliz"
    if marca.startswith("falso:"):
        if isinstance(inyectado, ModeloFalso):
            return inyectado
        return ModeloFalso(marca.split(":", 1)[1])
    return inyectado or ModeloReal()


class Agente:
    """Base de los 7 agentes con modelo."""

    nombre: str = ""
    contrato: type[BaseModel] = BaseModel
    campo: str = ""

    def prompt(self, estado: EstadoFabrica) -> str:
        """El turno de usuario, con cada dato entre delimitadores."""
        raise NotImplementedError

    def validar(self, salida: BaseModel, estado: EstadoFabrica) -> list[str]:
        """Problemas de negocio de la salida; vacío si es válida."""
        return []

    def guardar(self, salida: BaseModel, estado: EstadoFabrica) -> dict:
        """El update del estado cuando la salida es válida."""
        return {self.campo: salida.model_dump()}

    def resumen(self, salida: BaseModel) -> str:
        """Una línea para la bitácora."""
        return "OK"

    def ejecutar(self, estado: EstadoFabrica, modelo: Modelo) -> dict:
        """Llama al modelo con un reintento; devuelve el update del estado."""
        sistema = cargar_prompt(self.nombre)
        base = self.prompt(estado)
        esquema = self.contrato.model_json_schema()
        llamadas: list[dict] = []
        costo = 0.0
        problemas: list[str] = []
        for intento in range(1, config.MAX_INTENTOS + 1):
            texto = base
            if problemas:
                texto += "\n\n" + envolver("problemas_intento_anterior", "\n".join(
                    f"- {p}" for p in problemas)) + "\nCorrige esos problemas y responde de nuevo."
            try:
                r = modelo.llamar(self.nombre, sistema, texto, esquema)
            except ErrorModelo as e:
                problemas = [str(e)]
                llamadas.append({"agente": self.nombre, "intento": intento, "error": str(e)[:300]})
                continue
            costo += r.costo_usd
            llamadas.append({"agente": self.nombre, "intento": intento, "modelo": r.modelo,
                             "costo_usd": r.costo_usd, "turnos": r.turnos, "tokens": r.tokens,
                             "segundos": r.segundos})
            try:
                salida = self.contrato.model_validate(r.datos)
            except ValidationError as e:
                problemas = problemas_pydantic(e)
                continue
            problemas = self.validar(salida, estado)
            if not problemas:
                update = self.guardar(salida, estado)
                update.update({
                    "llamadas": llamadas,
                    "costo_usd": costo,
                    "bitacora": update.get("bitacora", [])
                    + [f"[{self.nombre}] {self.resumen(salida)}"],
                })
                return update
            log.registrar("salida_rechazada", hilo=estado.get("hilo", ""), hu=estado.get("hu", ""),
                          capa="validacion_salidas", nodo=self.nombre,
                          detalle=f"intento {intento}: " + " | ".join(problemas))
        return {
            "errores_agente": [{"agente": self.nombre, "problemas": problemas[:10]}],
            "llamadas": llamadas,
            "costo_usd": costo,
            "bitacora": [f"[{self.nombre}] contrato inválido tras {config.MAX_INTENTOS} intentos: "
                         + " | ".join(problemas)[:300]],
        }


def como_nodo(agente: Agente, modelo: Modelo | None) -> Callable[[EstadoFabrica], dict]:
    """Convierte un agente en un nodo de LangGraph."""

    def nodo(estado: EstadoFabrica) -> dict:
        return agente.ejecutar(estado, resolver_modelo(estado, modelo))

    nodo.__name__ = agente.nombre
    return nodo
