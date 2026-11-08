"""Especificador: historia + reglas de negocio → criterios de aceptación verificables."""

from fabrica import config
from fabrica.agentes.base import Agente, envolver
from fabrica.contratos import Especificacion, validar_especificacion
from fabrica.estado import EstadoFabrica


class Especificador(Agente):
    """Convierte la historia en una ``Especificacion``."""

    nombre = "especificador"
    contrato = Especificacion
    campo = "especificacion"

    def prompt(self, estado: EstadoFabrica) -> str:
        """Historia y reglas entre delimitadores; las respuestas de la persona si las hay."""
        partes = [
            "Escribe la especificación de la historia usando las reglas de negocio.",
            envolver("historia_no_confiable", estado.get("historia_texto", "")),
            envolver("reglas_negocio", config.ruta_reglas().read_text(encoding="utf-8")),
        ]
        if estado.get("respuestas_aclaracion"):
            partes.append(envolver("respuestas_operador", estado["respuestas_aclaracion"]))
        return "\n\n".join(partes)

    def validar(self, salida: Especificacion, estado: EstadoFabrica) -> list[str]:
        """Criterios suficientes, ids únicos, un criterio de error y reglas que existen."""
        return validar_especificacion(salida)

    def resumen(self, salida: Especificacion) -> str:
        """Criterios y preguntas abiertas."""
        ids = [c.id for c in salida.criterios]
        return (f"{len(ids)} criterios ({ids[0]}…{ids[-1]}) · "
                f"{len(salida.preguntas_abiertas)} preguntas abiertas")
