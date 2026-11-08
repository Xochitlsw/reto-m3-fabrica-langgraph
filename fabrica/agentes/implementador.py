"""Implementador: especificación + plan aprobado → el módulo de Python puro."""

from fabrica import config
from fabrica.agentes.base import Agente, envolver
from fabrica.contratos import Implementacion, Plan, validar_implementacion
from fabrica.estado import EstadoFabrica, huella
from fabrica.seguridad.revision_codigo import revisar


def tamano_codigo(*artefactos: dict | None) -> int:
    """Bytes de código en el estado (implementación + pruebas)."""
    return sum(len(a["contenido"].encode("utf-8"))
               for art in artefactos if art for a in art.get("archivos", []))


class Implementador(Agente):
    """Escribe el módulo; el código (no el modelo) decide si se acepta."""

    nombre = "implementador"
    contrato = Implementacion
    campo = "implementacion"

    def prompt(self, estado: EstadoFabrica) -> str:
        """Especificación y plan; en una corrección, el código anterior y la instrucción."""
        partes = ["Escribe el módulo que cumple el plan aprobado.",
                  envolver("especificacion", estado["especificacion"]),
                  envolver("plan", estado["plan"])]
        correccion = estado.get("correccion") or {}
        if correccion.get("responsable") == self.nombre and estado.get("implementacion"):
            archivos = estado["implementacion"]["archivos"]
            partes.append(envolver("codigo_no_confiable", archivos))
            partes.append(envolver("correccion", correccion))
        return "\n\n".join(partes)

    def validar(self, salida: Implementacion, estado: EstadoFabrica) -> list[str]:
        """Contrato de negocio, revisión estática con lista blanca y tope de tamaño."""
        plan = Plan.model_validate(estado["plan"])
        archivos = [a.model_dump() for a in salida.archivos]
        propios = [a["nombre"][:-3] for a in archivos]
        problemas = validar_implementacion(salida, plan)
        problemas += revisar(archivos, "implementacion", propios)
        if tamano_codigo(salida.model_dump(), estado.get("pruebas")) > config.MAX_CODIGO_ESTADO:
            problemas.append(f"El código pasa de {config.MAX_CODIGO_ESTADO} bytes en total.")
        return problemas

    def guardar(self, salida: Implementacion, estado: EstadoFabrica) -> dict:
        """La implementación con su huella (la vigencia se decide por hash)."""
        datos = salida.model_dump()
        return {self.campo: {**datos, "sha256": huella(datos)}}

    def resumen(self, salida: Implementacion) -> str:
        """Archivos escritos."""
        return ", ".join(a.nombre for a in salida.archivos)
