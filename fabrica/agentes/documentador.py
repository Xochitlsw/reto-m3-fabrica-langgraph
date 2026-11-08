"""Documentador: escribe el README del módulo generado."""

from fabrica.agentes.base import Agente, envolver
from fabrica.contratos import Documentacion, Plan, validar_documentacion
from fabrica.estado import EstadoFabrica


class Documentador(Agente):
    """Documenta uso, ejemplos, pruebas y limitaciones."""

    nombre = "documentador"
    contrato = Documentacion
    campo = "documentacion"

    def prompt(self, estado: EstadoFabrica) -> str:
        """Especificación, firmas, resumen de pruebas, revisión y observaciones de la persona."""
        plan = estado["plan"]
        ejecucion = estado.get("ejecucion") or {}
        partes = [
            "Escribe el README del módulo.",
            envolver("especificacion", estado["especificacion"]),
            envolver("firmas", {"modulo": plan["modulo"], "funciones": plan["funciones"]}),
            envolver("resumen_pruebas", {"casos": estado["pruebas"]["casos"],
                                         "aprobadas": ejecucion.get("aprobadas"),
                                         "fallidas": ejecucion.get("fallidas")}),
            envolver("revision", estado.get("revision") or {}),
        ]
        escalamiento = estado.get("decision_escalamiento") or {}
        if escalamiento.get("decision") == "aceptar":
            partes.append(envolver("observaciones_operador", escalamiento.get("comentario", "")))
        return "\n\n".join(partes)

    def validar(self, salida: Documentacion, estado: EstadoFabrica) -> list[str]:
        """Título, secciones, funciones mencionadas y tamaño."""
        return validar_documentacion(salida, Plan.model_validate(estado["plan"]))

    def resumen(self, salida: Documentacion) -> str:
        """Tamaño del README."""
        return f"README de {len(salida.readme.encode('utf-8'))} bytes"
