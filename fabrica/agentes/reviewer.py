"""Reviewer: revisa código, pruebas y ejecución contra la especificación, y hace el triage."""

from fabrica.agentes.base import Agente, envolver
from fabrica.contratos import Especificacion, Revision, validar_revision
from fabrica.estado import EstadoFabrica


class Reviewer(Agente):
    """Aprueba o pide corregir, con responsable y criterio («la especificación manda»)."""

    nombre = "reviewer"
    contrato = Revision
    campo = "revision"

    def prompt(self, estado: EstadoFabrica) -> str:
        """Especificación, plan, código, pruebas y el resultado del sandbox."""
        ejecucion = estado.get("ejecucion") or {}
        resumen = {k: ejecucion.get(k) for k in
                   ("ok", "aprobadas", "fallidas", "errores", "fallos", "problemas_estaticos")}
        return "\n\n".join([
            "Revisa el código y las pruebas contra la especificación.",
            envolver("especificacion", estado["especificacion"]),
            envolver("plan", estado["plan"]),
            envolver("codigo_no_confiable", estado["implementacion"]["archivos"]),
            envolver("pruebas_no_confiables", estado["pruebas"]["archivos"]),
            envolver("ejecucion", resumen),
        ])

    def validar(self, salida: Revision, estado: EstadoFabrica) -> list[str]:
        """Con «corregir»: responsable, criterio existente e instrucción."""
        return validar_revision(salida, Especificacion.model_validate(estado["especificacion"]))

    def guardar(self, salida: Revision, estado: EstadoFabrica) -> dict:
        """La revisión atada a lo que se evaluó."""
        evaluado = (estado.get("ejecucion") or {}).get("evaluado", "")
        return {self.campo: {**salida.model_dump(), "evaluado": evaluado}}

    def resumen(self, salida: Revision) -> str:
        """Veredicto y, si toca, responsable y criterio."""
        if salida.veredicto == "aprobar":
            return "aprobar"
        return f"corregir · {salida.responsable} · {salida.criterio}"
