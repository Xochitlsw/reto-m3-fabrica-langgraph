"""Antigüedad de empleados en años y meses completos (HU-05).

Funciones para calcular la antigüedad de un empleado a una fecha de corte
(por omisión, hoy) y para obtener la lista de empleados activos ordenada por
antigüedad, pensada para preparar reconocimientos por aniversario.

Reglas aplicadas:
- 8: la antigüedad se expresa en años y meses completos; los días sobrantes
  no cuentan.
- 9: sin fecha de corte se usa la fecha de hoy; se permite un corte futuro.
- 10: un mes se completa el mismo día del mes siguiente o, si ese día no
  existe, el último día de ese mes.
- 11: para un empleado dado de baja se cuenta hasta la fecha más temprana
  entre la baja y el corte; la lista de reconocimientos solo incluye activos.
- 12: error si la fecha de ingreso es posterior a la fecha de corte.
- 13: singular cuando corresponde y siempre las dos partes (años y meses).
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

ESTADO_ACTIVO = "activo"
ESTADO_BAJA = "baja"
ESTADOS_VALIDOS = (ESTADO_ACTIVO, ESTADO_BAJA)

MENSAJE_INGRESO_POSTERIOR = (
    "La fecha de ingreso no puede ser posterior a la fecha de corte"
)


@dataclass(frozen=True)
class Empleado:
    """Datos mínimos de un empleado ya cargado para calcular su antigüedad.

    Atributos:
        numero: número de empleado (formato fijo, por ejemplo «EMP-0001»).
        nombre: nombre del empleado; solo se copia a los resultados.
        fecha_ingreso: fecha de ingreso a la empresa.
        estado: «activo» o «baja».
        fecha_baja: fecha de baja; obligatoria si el estado es «baja».
    """

    numero: str
    nombre: str
    fecha_ingreso: date
    estado: str = ESTADO_ACTIVO
    fecha_baja: date | None = None


def hoy() -> date:
    """Devuelve la fecha de hoy.

    Es la fecha de corte por omisión. Se evalúa en tiempo de ejecución (nunca
    como valor por defecto de un parámetro) para que no quede congelada al
    importar el módulo.
    """
    return date.today()


def meses_completos(desde: date, hasta: date) -> int:
    """Calcula los meses completos transcurridos entre dos fechas.

    Un mes se completa el mismo día del mes siguiente o, si ese día no existe
    en el mes, el último día de ese mes.

    Args:
        desde: fecha de inicio (por ejemplo, el ingreso).
        hasta: fecha final (por ejemplo, el corte).

    Returns:
        Número entero de meses completos (0 si ambas fechas son iguales).

    Raises:
        ValueError: si ``desde`` es posterior a ``hasta``.
    """
    if desde > hasta:
        raise ValueError(MENSAJE_INGRESO_POSTERIOR)

    meses = (hasta.year - desde.year) * 12 + (hasta.month - desde.month)
    ultimo_dia_hasta = calendar.monthrange(hasta.year, hasta.month)[1]
    dia_de_cumplimiento = min(desde.day, ultimo_dia_hasta)
    if hasta.day < dia_de_cumplimiento:
        meses -= 1
    return meses


def formatear_antiguedad(anios: int, meses: int) -> str:
    """Da formato «N años y M meses» a una antigüedad.

    Usa singular con 1 («1 año», «1 mes») y muestra siempre las dos partes,
    aunque valgan 0.

    Args:
        anios: años completos (no negativo).
        meses: meses completos sobrantes (no negativo).

    Returns:
        Texto, por ejemplo «7 años y 8 meses» o «1 año y 0 meses».

    Raises:
        ValueError: si alguno de los valores es negativo.
    """
    if anios < 0 or meses < 0:
        raise ValueError("Los años y los meses no pueden ser negativos")
    texto_anios = "1 año" if anios == 1 else f"{anios} años"
    texto_meses = "1 mes" if meses == 1 else f"{meses} meses"
    return f"{texto_anios} y {texto_meses}"


def _fecha_fin(empleado: Empleado, fecha_corte: date) -> date:
    """Valida al empleado y devuelve la fecha hasta la que se cuenta.

    Orden de validación:
    1. Estado desconocido, o «baja» sin fecha de baja.
    2. Ingreso posterior a la fecha de corte (mensaje exacto de la regla 12).
    3. Fecha de baja anterior al ingreso.
    """
    if empleado.estado not in ESTADOS_VALIDOS:
        raise ValueError(f"Estado de empleado desconocido: {empleado.estado!r}")
    if empleado.estado == ESTADO_BAJA and empleado.fecha_baja is None:
        raise ValueError("Un empleado dado de baja requiere fecha de baja")

    if empleado.fecha_ingreso > fecha_corte:
        raise ValueError(MENSAJE_INGRESO_POSTERIOR)

    if empleado.estado == ESTADO_BAJA:
        if empleado.fecha_baja < empleado.fecha_ingreso:
            raise ValueError(
                "La fecha de baja no puede ser anterior a la fecha de ingreso"
            )
        return min(empleado.fecha_baja, fecha_corte)

    return fecha_corte


def meses_de_antiguedad(empleado: Empleado, fecha_corte: date | None = None) -> int:
    """Calcula la antigüedad total de un empleado en meses completos.

    Si ``fecha_corte`` es None se usa la fecha de hoy. Se permite un corte
    futuro. Si el estado es «baja», se cuenta hasta la fecha más temprana
    entre la baja y el corte.

    Args:
        empleado: empleado ya cargado.
        fecha_corte: fecha de corte, o None para usar hoy.

    Returns:
        Meses completos de antigüedad.

    Raises:
        ValueError: estado desconocido, «baja» sin fecha de baja, ingreso
            posterior al corte («La fecha de ingreso no puede ser posterior a
            la fecha de corte») o baja anterior al ingreso.
    """
    corte = hoy() if fecha_corte is None else fecha_corte
    fin = _fecha_fin(empleado, corte)
    return meses_completos(empleado.fecha_ingreso, fin)


def calcular_antiguedad(empleado: Empleado, fecha_corte: date | None = None) -> str:
    """Calcula la antigüedad de un empleado como texto.

    Args:
        empleado: empleado ya cargado.
        fecha_corte: fecha de corte, o None para usar hoy.

    Returns:
        Texto como «7 años y 8 meses».

    Raises:
        ValueError: en los mismos casos que ``meses_de_antiguedad``.
    """
    meses_totales = meses_de_antiguedad(empleado, fecha_corte)
    anios, meses = divmod(meses_totales, 12)
    return formatear_antiguedad(anios, meses)


def lista_reconocimientos(
    empleados: list[Empleado], fecha_corte: date | None = None
) -> list[tuple[str, str, str]]:
    """Lista de empleados activos ordenada por antigüedad para reconocimientos.

    Solo incluye empleados activos (los dados de baja se descartan sin
    validarlos). El orden es de mayor a menor antigüedad en meses completos y,
    en caso de empate, por número de empleado ascendente. Con ``fecha_corte``
    None se usa hoy() una sola vez para toda la lista.

    Si un empleado activo tiene ingreso posterior al corte, se lanza el
    ValueError de la regla 12 para toda la lista (no se omite en silencio).

    Args:
        empleados: empleados ya cargados.
        fecha_corte: fecha de corte, o None para usar hoy.

    Returns:
        Lista de tuplas ``(numero, nombre, antigüedad en texto)``.

    Raises:
        ValueError: si algún empleado no descartado es inválido.
    """
    corte = hoy() if fecha_corte is None else fecha_corte

    calculados: list[tuple[int, str, str]] = []
    for empleado in empleados:
        if empleado.estado == ESTADO_BAJA:
            continue
        meses_totales = meses_de_antiguedad(empleado, corte)
        calculados.append((meses_totales, empleado.numero, empleado.nombre))

    calculados.sort(key=lambda fila: (-fila[0], fila[1]))

    resultado: list[tuple[str, str, str]] = []
    for meses_totales, numero, nombre in calculados:
        anios, meses = divmod(meses_totales, 12)
        resultado.append((numero, nombre, formatear_antiguedad(anios, meses)))
    return resultado
