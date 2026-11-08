"""Tester: especificación + firmas del plan → pruebas pytest. No ve el código (juez aparte)."""

from fabrica import config
from fabrica.agentes.base import Agente, envolver
from fabrica.agentes.implementador import tamano_codigo
from fabrica.contratos import Especificacion, Pruebas, validar_pruebas
from fabrica.estado import EstadoFabrica, huella
from fabrica.seguridad.revision_codigo import revisar


class Tester(Agente):
    """Escribe las pruebas a partir de la especificación y de la interfaz, no del código."""

    nombre = "tester"
    contrato = Pruebas
    campo = "pruebas"

    def prompt(self, estado: EstadoFabrica) -> str:
        """Especificación y firmas; en una corrección, las pruebas anteriores y la instrucción."""
        plan = estado["plan"]
        firmas = {"modulo": plan["modulo"], "funciones": plan["funciones"]}
        partes = ["Escribe las pruebas pytest a partir de la especificación y las firmas.",
                  envolver("especificacion", estado["especificacion"]),
                  envolver("firmas", firmas)]
        correccion = estado.get("correccion") or {}
        if correccion.get("responsable") == self.nombre and estado.get("pruebas"):
            partes.append(envolver("pruebas_no_confiables", estado["pruebas"]["archivos"]))
            partes.append(envolver("correccion", correccion))
        return "\n\n".join(partes)

    def validar(self, salida: Pruebas, estado: EstadoFabrica) -> list[str]:
        """Trazabilidad, fechas explícitas, revisión estática y tope de tamaño."""
        esp = Especificacion.model_validate(estado["especificacion"])
        problemas = validar_pruebas(salida, esp)
        archivos = [a.model_dump() for a in salida.archivos]
        problemas += revisar(archivos, "pruebas", [estado["plan"]["modulo"]])
        total = tamano_codigo(salida.model_dump(), estado.get("implementacion"))
        if total > config.MAX_CODIGO_ESTADO:
            problemas.append(f"El código pasa de {config.MAX_CODIGO_ESTADO} bytes en total.")
        return problemas

    def guardar(self, salida: Pruebas, estado: EstadoFabrica) -> dict:
        """Las pruebas con su huella."""
        datos = salida.model_dump()
        return {self.campo: {**datos, "sha256": huella(datos)}}

    def resumen(self, salida: Pruebas) -> str:
        """Archivos y casos."""
        return f"{len(salida.casos)} casos en {', '.join(a.nombre for a in salida.archivos)}"
