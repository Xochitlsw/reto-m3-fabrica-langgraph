"""Contratos Pydantic de cada agente y sus validadores deterministas (docs/diseno.md, sección 1.2).

«El modelo propone y el código decide»: cada salida de un agente cumple su contrato y después pasa
por un validador que devuelve la lista de problemas (vacía = válido), como ``problemas_de`` en M3B.
Los problemas se escriben para que el agente los lea y corrija en su reintento.

En los contratos que deciden, el razonamiento va antes que la decisión (``motivo`` antes que
``sospechosa``; ``observaciones`` antes que ``veredicto``).
"""

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from fabrica import config

ID_CRITERIO = r"^C-\d{2}$"
ID_CASO = r"^CP-\d{2}$"
NOMBRE_ARCHIVO = r"^[a-z_][a-z0-9_]*\.py$"
NOMBRE_MODULO = r"^[a-z_][a-z0-9_]*$"
MAX_ARCHIVO = 20_000
MAX_PASOS_PLAN = 10
MAX_LINEAS_PLAN = 60
MAX_README = 8_000
SECCIONES_README = ("Uso", "Ejemplos", "Pruebas", "Limitaciones")
# Un criterio «de error» describe un rechazo o un mensaje de error.
_PATRON_ERROR = re.compile(r"error|inv[aá]lid|rechaz|no puede|no se permite", re.IGNORECASE)
_PATRON_FECHA_HOY = re.compile(r"\b(today|now|utcnow)\s*\(")


# --- Filtro de seguridad (capa 2 del guardián) ---------------------------------------------------
class Veredicto(BaseModel):
    """¿La historia trae instrucciones dirigidas a una IA en lugar de requisitos del producto?"""

    motivo: str = Field(description="Por qué es o no sospechosa, en una o dos frases")
    sospechosa: bool


# --- Especificador ------------------------------------------------------------------------------
class Criterio(BaseModel):
    """Un criterio de aceptación en formato Dado/Cuando/Entonces."""

    id: str = Field(pattern=ID_CRITERIO, description="C-01, C-02…")
    descripcion: str
    dado: str
    cuando: str
    entonces: str


class Ejemplo(BaseModel):
    """Un ejemplo concreto de entrada y salida esperada (todos los valores como texto)."""

    entrada: dict[str, str]
    salida_esperada: str


class Especificacion(BaseModel):
    """Lo que entrega el especificador: la historia convertida en criterios verificables."""

    historia: str = Field(description="Id de la historia, por ejemplo HU-05")
    objetivo: str
    criterios: list[Criterio]
    reglas_aplicadas: list[int] = Field(description="Números de regla de reglas_negocio.md")
    ejemplos: list[Ejemplo]
    fuera_de_alcance: list[str]
    preguntas_abiertas: list[str] = Field(
        description="El lugar legítimo para decir «no lo sé»; vacío si no hay dudas"
    )


# --- Planificador -------------------------------------------------------------------------------
class Firma(BaseModel):
    """La interfaz tipada de una función pública del módulo."""

    nombre: str = Field(pattern=NOMBRE_MODULO)
    firma: str = Field(description="def nombre(param: tipo, ...) -> tipo")
    descripcion: str
    criterios: list[str] = Field(description="Ids C-NN que cubre esta función")


class Plan(BaseModel):
    """Lo que entrega el planificador y aprueba una persona."""

    modulo: str = Field(pattern=NOMBRE_MODULO, description="Nombre del módulo sin .py")
    funciones: list[Firma]
    pasos: list[str]
    casos_borde: list[str]
    riesgos: list[str]


# --- Implementador y tester ---------------------------------------------------------------------
class Archivo(BaseModel):
    """Un archivo de Python que el código (no el modelo) escribe dentro del sandbox."""

    nombre: str = Field(pattern=NOMBRE_ARCHIVO)
    contenido: str = Field(max_length=MAX_ARCHIVO)


class Implementacion(BaseModel):
    """Lo que entrega el implementador: el módulo del plan (1 a 3 archivos)."""

    archivos: list[Archivo] = Field(min_length=1, max_length=3)
    notas: str


class CasoPrueba(BaseModel):
    """Un caso de prueba trazable a un criterio de aceptación."""

    id: str = Field(pattern=ID_CASO, description="CP-01, CP-02…")
    criterio: str = Field(pattern=ID_CRITERIO)
    descripcion: str


class Pruebas(BaseModel):
    """Lo que entrega el tester: pruebas pytest escritas desde la especificación y las firmas."""

    archivos: list[Archivo] = Field(min_length=1, max_length=2)
    casos: list[CasoPrueba]


# --- Reviewer -----------------------------------------------------------------------------------
class Revision(BaseModel):
    """Lo que entrega el reviewer: el veredicto y, si hay que corregir, quién y qué (triage)."""

    observaciones: str
    criterio: str | None = Field(default=None, description="C-NN que no se cumple, si lo hay")
    veredicto: Literal["aprobar", "corregir"]
    responsable: Literal["implementador", "tester"] | None = None
    instruccion: str = ""


# --- Documentador -------------------------------------------------------------------------------
class Documentacion(BaseModel):
    """Lo que entrega el documentador: el README del módulo generado."""

    readme: str


# --- Pausas humanas y sandbox (los produce el código, no el modelo) -----------------------------
Pausa = Literal["plan", "aclaracion", "escalamiento"]
Decision = Literal["aprobar", "rechazar", "continuar", "responder", "aceptar", "terminar"]

DECISIONES_POR_PAUSA: dict[str, tuple[str, ...]] = {
    "aclaracion": ("continuar", "responder", "terminar"),
    "plan": ("aprobar", "rechazar", "terminar"),
    "escalamiento": ("aceptar", "terminar"),
}
DECISIONES_CON_COMENTARIO = ("rechazar", "responder", "aceptar")


class RespuestaHumana(BaseModel):
    """La decisión de una persona identificada, atada al sha256 de lo que se le mostró."""

    pausa: Pausa
    decision: Decision
    comentario: str = Field(default="", max_length=2000)
    operador: str = Field(min_length=1, max_length=40)
    sobre_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ResultadoEjecucion(BaseModel):
    """Resultado de correr las pruebas en el sandbox."""

    ok: bool
    evaluado: str
    aprobadas: int = 0
    fallidas: int = 0
    errores: int = 0
    segundos: float = 0.0
    fallos: list[str] = []
    log: str = Field(default="", max_length=4000)
    problemas_estaticos: list[str] = []
    aislamiento: Literal["sandbox-exec", "subproceso"] = "subproceso"


# --- Utilidades ---------------------------------------------------------------------------------
def problemas_pydantic(error: ValidationError) -> list[str]:
    """Errores de Pydantic, cortos y accionables (como ``validar_json`` de M3B)."""
    return [
        "El JSON no cumple el contrato: "
        + "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors()[:5])
    ]


def reglas_disponibles(ruta: Path | None = None) -> set[int]:
    """Números de regla de ``reglas_negocio.md``, leídos del archivo (no hay un tope fijo)."""
    ruta = ruta or config.ruta_reglas()
    texto = ruta.read_text(encoding="utf-8")
    return {int(n) for n in re.findall(r"^(\d+)\.\s", texto, flags=re.MULTILINE)}


def _fuga(*textos: str) -> list[str]:
    """Problema si algún texto contiene la bandera del señuelo."""
    if any(config.BANDERA in t for t in textos):
        return [f"La salida contiene {config.BANDERA}: posible fuga del señuelo."]
    return []


# --- Validadores de negocio ---------------------------------------------------------------------
def validar_especificacion(esp: Especificacion, reglas: set[int] | None = None) -> list[str]:
    """≥ 2 criterios, ids únicos, ≥ 1 criterio de error y reglas citadas que existen."""
    reglas = reglas_disponibles() if reglas is None else reglas
    problemas = []
    if len(esp.criterios) < 2:
        problemas.append("Se esperan al menos 2 criterios (camino feliz y un error).")
    ids = [c.id for c in esp.criterios]
    if len(ids) != len(set(ids)):
        problemas.append("Hay ids de criterio repetidos.")
    if not any(_PATRON_ERROR.search(f"{c.descripcion} {c.entonces}") for c in esp.criterios):
        problemas.append("Falta al menos un criterio de error (qué pasa con una entrada inválida).")
    inexistentes = sorted(set(esp.reglas_aplicadas) - reglas)
    if inexistentes:
        problemas.append(
            f"Reglas que no existen en reglas_negocio.md: {inexistentes}; "
            f"las disponibles son {min(reglas)}–{max(reglas)}."
        )
    problemas += _fuga(esp.model_dump_json())
    return problemas


def renderizar_plan(plan: Plan) -> str:
    """El plan en markdown, tal como lo ve la persona que lo aprueba."""
    lineas = [f"### Plan · `{plan.modulo}.py`", "", "**Funciones**"]
    for f in plan.funciones:
        lineas.append(f"- `{f.firma}` — {f.descripcion} ({', '.join(f.criterios)})")
    lineas += ["", "**Pasos**"] + [f"{i}. {p}" for i, p in enumerate(plan.pasos, 1)]
    if plan.casos_borde:
        lineas += ["", "**Casos borde**"] + [f"- {c}" for c in plan.casos_borde]
    if plan.riesgos:
        lineas += ["", "**Riesgos**"] + [f"- {r}" for r in plan.riesgos]
    return "\n".join(lineas)


def validar_plan(plan: Plan, esp: Especificacion) -> list[str]:
    """Cada criterio cubierto por una función, ≤ 10 pasos y ≤ 60 líneas renderizado."""
    problemas = []
    if plan.modulo.startswith("test_"):
        problemas.append("El módulo no puede empezar con test_.")
    if not plan.funciones:
        problemas.append("El plan no tiene funciones.")
    existentes = {c.id for c in esp.criterios}
    cubiertos = {c for f in plan.funciones for c in f.criterios}
    faltan = sorted(existentes - cubiertos)
    if faltan:
        problemas.append(f"Criterios sin función que los cubra: {faltan}.")
    sobran = sorted(cubiertos - existentes)
    if sobran:
        problemas.append(f"Criterios que no existen en la especificación: {sobran}.")
    if len(plan.pasos) > MAX_PASOS_PLAN:
        problemas.append(f"El plan tiene {len(plan.pasos)} pasos; máximo {MAX_PASOS_PLAN}.")
    lineas = [x for x in renderizar_plan(plan).splitlines() if x.strip()]
    if len(lineas) > MAX_LINEAS_PLAN:
        problemas.append(
            f"El plan tiene {len(lineas)} líneas; resúmelo en {MAX_LINEAS_PLAN} como máximo."
        )
    problemas += _fuga(plan.model_dump_json())
    return problemas


def validar_implementacion(impl: Implementacion, plan: Plan) -> list[str]:
    """Nombres válidos, sin pruebas, incluye el módulo del plan y sin repetidos."""
    problemas = []
    nombres = [a.nombre for a in impl.archivos]
    if len(nombres) != len(set(nombres)):
        problemas.append("Hay archivos repetidos.")
    if any(n.startswith("test_") or n == "conftest.py" for n in nombres):
        problemas.append("La implementación no lleva pruebas ni conftest.py: eso es del tester.")
    if f"{plan.modulo}.py" not in nombres:
        problemas.append(f"Falta el módulo del plan: {plan.modulo}.py.")
    problemas += _fuga(*(a.contenido for a in impl.archivos), impl.notas)
    return problemas


def validar_pruebas(pru: Pruebas, esp: Especificacion) -> list[str]:
    """Trazabilidad C-NN ↔ CP-NN, cada caso en el código y fechas de corte explícitas."""
    problemas = []
    nombres = [a.nombre for a in pru.archivos]
    if any(not n.startswith("test_") for n in nombres):
        problemas.append("Los archivos de pruebas se llaman test_*.py.")
    existentes = {c.id for c in esp.criterios}
    cubiertos = {c.criterio for c in pru.casos}
    faltan = sorted(existentes - cubiertos)
    if faltan:
        problemas.append(f"Criterios sin caso de prueba: {faltan}.")
    sobran = sorted(cubiertos - existentes)
    if sobran:
        problemas.append(f"Casos que citan criterios inexistentes: {sobran}.")
    ids = [c.id for c in pru.casos]
    if len(ids) != len(set(ids)):
        problemas.append("Hay ids de caso repetidos.")
    codigo = "\n".join(a.contenido for a in pru.archivos)
    sin_test = [i for i in ids if i not in codigo]
    if sin_test:
        problemas.append(f"Casos que no aparecen en el código de las pruebas: {sin_test}.")
    if _PATRON_FECHA_HOY.search(codigo):
        problemas.append("Las pruebas usan today()/now(): fija la fecha de corte explícitamente.")
    problemas += _fuga(codigo)
    return problemas


def validar_revision(rev: Revision, esp: Especificacion) -> list[str]:
    """Con «corregir» exige responsable, un criterio existente e instrucción."""
    problemas = []
    if rev.veredicto == "corregir":
        if rev.responsable is None:
            problemas.append("Con «corregir» nombra al responsable: implementador o tester.")
        if rev.criterio not in {c.id for c in esp.criterios}:
            problemas.append("Con «corregir» cita el criterio C-NN de la especificación que falla.")
        if not rev.instruccion.strip():
            problemas.append("Con «corregir» escribe la instrucción para el responsable.")
    problemas += _fuga(rev.model_dump_json())
    return problemas


def validar_documentacion(doc: Documentacion, plan: Plan) -> list[str]:
    """Empieza con «# », trae las secciones pedidas, nombra cada función y mide ≤ 8 KB."""
    problemas = []
    texto = doc.readme
    if not texto.startswith("# "):
        problemas.append("El README empieza con un título «# ».")
    for seccion in SECCIONES_README:
        if not re.search(rf"^##\s+{seccion}\b", texto, flags=re.MULTILINE):
            problemas.append(f"Falta la sección «## {seccion}».")
    faltan = [f.nombre for f in plan.funciones if f.nombre not in texto]
    if faltan:
        problemas.append(f"El README no menciona estas funciones: {faltan}.")
    if len(texto.encode("utf-8")) > MAX_README:
        problemas.append(f"El README pasa de {MAX_README} bytes.")
    problemas += _fuga(texto)
    return problemas


def validar_respuesta(
    resp: RespuestaHumana, pausa: str, sha_esperado: str, operadores: list[str]
) -> list[str]:
    """La decisión corresponde a la pausa, el operador está permitido y el sha coincide."""
    problemas = []
    if resp.pausa != pausa:
        problemas.append(f"La respuesta es para la pausa «{resp.pausa}», no para «{pausa}».")
    if resp.decision not in DECISIONES_POR_PAUSA[pausa]:
        opciones = ", ".join(DECISIONES_POR_PAUSA[pausa])
        problemas.append(f"Decisión «{resp.decision}» no válida aquí; opciones: {opciones}.")
    if resp.decision in DECISIONES_CON_COMENTARIO and not resp.comentario.strip():
        problemas.append(f"La decisión «{resp.decision}» necesita un comentario.")
    if resp.operador not in operadores:
        problemas.append(f"El operador «{resp.operador}» no está en la lista permitida.")
    if resp.sobre_sha256 != sha_esperado:
        problemas.append("El sha256 no coincide con lo que se mostró: vuelve a revisar la pausa.")
    return problemas
