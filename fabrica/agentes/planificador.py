"""Planificador: especificación → plan con firmas tipadas, que aprueba una persona."""

from fabrica.agentes.base import Agente, envolver
from fabrica.contratos import Especificacion, Plan, validar_plan
from fabrica.estado import EstadoFabrica


class Planificador(Agente):
    """Propone el módulo, sus funciones (firmas) y los pasos."""

    nombre = "planificador"
    contrato = Plan
    campo = "plan"

    def prompt(self, estado: EstadoFabrica) -> str:
        """La especificación; si la persona rechazó el plan, el anterior y su comentario."""
        partes = ["Escribe el plan del módulo que cumple la especificación.",
                  envolver("especificacion", estado["especificacion"])]
        decision = estado.get("decision_plan") or {}
        if decision.get("decision") == "rechazar" and estado.get("plan"):
            partes.append(envolver("plan_anterior", estado["plan"]))
            partes.append(envolver("comentario_operador", decision.get("comentario", "")))
        return "\n\n".join(partes)

    def validar(self, salida: Plan, estado: EstadoFabrica) -> list[str]:
        """Cobertura de criterios, número de pasos y largo renderizado."""
        return validar_plan(salida, Especificacion.model_validate(estado["especificacion"]))

    def resumen(self, salida: Plan) -> str:
        """Módulo y número de funciones."""
        return f"{salida.modulo}.py · {len(salida.funciones)} funciones"
