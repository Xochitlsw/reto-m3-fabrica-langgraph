"""Pruebas de HU-05: antigüedad de empleados en años y meses completos.

Todas las fechas son explícitas. Para el corte por omisión (C-02) no se
sustituye nada: se compara contra hoy() pasado de forma explícita.
"""
from datetime import date

import pytest

import antiguedad_empleados as ae

MENSAJE_ERROR = "La fecha de ingreso no puede ser posterior a la fecha de corte"


class _EmpleadoFalso:
    """Respaldo con los mismos atributos por si Empleado no admite palabras clave."""

    numero = None
    nombre = None
    fecha_ingreso = None
    estado = None
    fecha_baja = None


def _emp(numero="EMP-0001", ingreso=date(2019, 3, 4), estado="activo",
         baja=None, nombre="Persona Prueba"):
    """Construye un empleado con los datos ya cargados."""
    try:
        return ae.Empleado(
            numero=numero,
            nombre=nombre,
            fecha_ingreso=ingreso,
            estado=estado,
            fecha_baja=baja,
        )
    except (TypeError, AttributeError):
        falso = _EmpleadoFalso()
        falso.numero = numero
        falso.nombre = nombre
        falso.fecha_ingreso = ingreso
        falso.estado = estado
        falso.fecha_baja = baja
        return falso


def _baja_2023():
    return _emp("EMP-0002", date(2019, 3, 4), "baja", date(2023, 6, 15))


# ---------------------------------------------------------------- C-01

def test_cp01_camino_feliz_anios_y_meses():
    """CP-01: 2019-03-04 -> 2026-11-08 es «7 años y 8 meses»."""
    emp = _emp(ingreso=date(2019, 3, 4))
    corte = date(2026, 11, 8)
    assert ae.calcular_antiguedad(emp, corte) == "7 años y 8 meses"
    assert ae.meses_de_antiguedad(emp, corte) == 92
    assert ae.meses_completos(date(2019, 3, 4), corte) == 92


# ---------------------------------------------------------------- C-02

def test_cp02_hoy_devuelve_una_fecha():
    """CP-02: hoy() devuelve un date (fecha de corte por omisión)."""
    assert isinstance(ae.hoy(), date)


def test_cp02_sin_corte_equivale_a_pasar_hoy():
    """CP-02: sin fecha de corte se usa hoy(); mismo resultado que pasarlo explícito."""
    emp = _emp(ingreso=date(2019, 3, 4))
    antes = ae.hoy()
    texto = ae.calcular_antiguedad(emp)
    meses = ae.meses_de_antiguedad(emp)
    despues = ae.hoy()
    assert texto in (
        ae.calcular_antiguedad(emp, antes),
        ae.calcular_antiguedad(emp, despues),
    )
    assert meses in (
        ae.meses_de_antiguedad(emp, antes),
        ae.meses_de_antiguedad(emp, despues),
    )


def test_cp02_ingreso_hoy_sin_corte_es_cero():
    """CP-02: un empleado que ingresa hoy tiene «0 años y 0 meses» sin indicar corte."""
    emp = _emp(ingreso=ae.hoy())
    assert ae.calcular_antiguedad(emp) == "0 años y 0 meses"
    assert ae.meses_de_antiguedad(emp) == 0


def test_cp02_lista_sin_corte_usa_hoy():
    """CP-02: la lista para reconocimientos sin corte equivale a pasar hoy()."""
    empleados = [
        _emp("EMP-0002", date(2019, 3, 4)),
        _emp("EMP-0001", date(2015, 6, 10)),
    ]
    antes = ae.hoy()
    resultado = ae.lista_reconocimientos(empleados)
    despues = ae.hoy()
    assert resultado in (
        ae.lista_reconocimientos(empleados, antes),
        ae.lista_reconocimientos(empleados, despues),
    )


# ---------------------------------------------------------------- C-03

def test_cp03_dias_sobrantes_no_cuentan():
    """CP-03: 2020-01-15 -> 2026-11-14 es «6 años y 9 meses»; el 15 completa el mes 10."""
    emp = _emp(ingreso=date(2020, 1, 15))
    assert ae.calcular_antiguedad(emp, date(2026, 11, 14)) == "6 años y 9 meses"
    assert ae.meses_de_antiguedad(emp, date(2026, 11, 14)) == 81
    assert ae.calcular_antiguedad(emp, date(2026, 11, 15)) == "6 años y 10 meses"


# ---------------------------------------------------------------- C-04

def test_cp04_mes_se_completa_el_mismo_dia():
    """CP-04: ingreso 2026-01-15; corte 02-15 -> 1 mes; corte 02-14 -> 0 meses."""
    emp = _emp(ingreso=date(2026, 1, 15))
    assert ae.calcular_antiguedad(emp, date(2026, 2, 15)) == "0 años y 1 mes"
    assert ae.calcular_antiguedad(emp, date(2026, 2, 14)) == "0 años y 0 meses"
    assert ae.meses_completos(date(2026, 1, 15), date(2026, 2, 15)) == 1
    assert ae.meses_completos(date(2026, 1, 15), date(2026, 2, 14)) == 0


# ---------------------------------------------------------------- C-05

def test_cp05_dia_inexistente_usa_ultimo_dia_del_mes():
    """CP-05: ingreso 2026-01-31; cortes 02-28 -> 1 mes, 02-27 -> 0, 03-30 -> 1."""
    emp = _emp(ingreso=date(2026, 1, 31))
    assert ae.calcular_antiguedad(emp, date(2026, 2, 28)) == "0 años y 1 mes"
    assert ae.calcular_antiguedad(emp, date(2026, 2, 27)) == "0 años y 0 meses"
    assert ae.calcular_antiguedad(emp, date(2026, 3, 30)) == "0 años y 1 mes"
    assert ae.meses_completos(date(2026, 1, 31), date(2026, 2, 28)) == 1
    assert ae.meses_completos(date(2026, 1, 31), date(2026, 2, 27)) == 0
    assert ae.meses_completos(date(2026, 1, 31), date(2026, 3, 30)) == 1


def test_cp05_segundo_mes_se_completa_el_31_de_marzo():
    """CP-05: ingreso 2026-01-31; el segundo mes se completa el 2026-03-31."""
    emp = _emp(ingreso=date(2026, 1, 31))
    assert ae.calcular_antiguedad(emp, date(2026, 3, 31)) == "0 años y 2 meses"
    assert ae.meses_completos(date(2026, 1, 31), date(2026, 3, 31)) == 2


def test_cp05_anio_bisiesto_y_mes_de_30_dias():
    """CP-05: febrero bisiesto (29) y abril (30) también usan el último día del mes."""
    # 2024 es bisiesto: el 2024-02-29 existe.
    assert ae.meses_completos(date(2024, 1, 31), date(2024, 2, 29)) == 1
    assert ae.meses_completos(date(2024, 1, 31), date(2024, 2, 28)) == 0
    # Abril tiene 30 días.
    assert ae.meses_completos(date(2026, 3, 31), date(2026, 4, 30)) == 1
    assert ae.meses_completos(date(2026, 3, 31), date(2026, 4, 29)) == 0


def test_cp05_ingreso_29_febrero_cumple_anio_el_28():
    """CP-05: ingreso 2024-02-29; el mes 12 se completa el 2025-02-28 (no existe el 29)."""
    emp = _emp(ingreso=date(2024, 2, 29))
    assert ae.calcular_antiguedad(emp, date(2025, 2, 28)) == "1 año y 0 meses"
    assert ae.calcular_antiguedad(emp, date(2025, 2, 27)) == "0 años y 11 meses"


# ---------------------------------------------------------------- C-06

def test_cp06_singular_anio_y_mes():
    """CP-06: 2025-10-08 -> 2026-11-08 es «1 año y 1 mes»."""
    emp = _emp(ingreso=date(2025, 10, 8))
    assert ae.calcular_antiguedad(emp, date(2026, 11, 8)) == "1 año y 1 mes"


def test_cp06_formatear_singular_y_plural():
    """CP-06: formatear_antiguedad usa singular solo con 1."""
    assert ae.formatear_antiguedad(1, 1) == "1 año y 1 mes"
    assert ae.formatear_antiguedad(2, 1) == "2 años y 1 mes"
    assert ae.formatear_antiguedad(1, 2) == "1 año y 2 meses"
    assert ae.formatear_antiguedad(7, 8) == "7 años y 8 meses"
    assert ae.formatear_antiguedad(11, 11) == "11 años y 11 meses"


# ---------------------------------------------------------------- C-07

@pytest.mark.parametrize(
    "ingreso, esperado",
    [
        (date(2026, 10, 8), "0 años y 1 mes"),
        (date(2025, 11, 8), "1 año y 0 meses"),
        (date(2026, 11, 8), "0 años y 0 meses"),
    ],
)
def test_cp07_siempre_las_dos_partes(ingreso, esperado):
    """CP-07: se muestran las dos partes aunque valgan 0; ingreso == corte no es error."""
    emp = _emp(ingreso=ingreso)
    assert ae.calcular_antiguedad(emp, date(2026, 11, 8)) == esperado


def test_cp07_formatear_ceros():
    """CP-07: formatear_antiguedad muestra siempre ambas partes."""
    assert ae.formatear_antiguedad(0, 1) == "0 años y 1 mes"
    assert ae.formatear_antiguedad(1, 0) == "1 año y 0 meses"
    assert ae.formatear_antiguedad(0, 0) == "0 años y 0 meses"
    assert ae.formatear_antiguedad(0, 5) == "0 años y 5 meses"
    assert ae.formatear_antiguedad(5, 0) == "5 años y 0 meses"


def test_cp07_meses_completos_misma_fecha_es_cero():
    """CP-07: meses_completos con desde == hasta devuelve 0."""
    assert ae.meses_completos(date(2026, 11, 8), date(2026, 11, 8)) == 0


# ---------------------------------------------------------------- C-08

def test_cp08_baja_cuenta_hasta_fecha_de_baja():
    """CP-08: baja 2023-06-15, corte 2026-11-08 -> «4 años y 3 meses»."""
    emp = _baja_2023()
    assert ae.calcular_antiguedad(emp, date(2026, 11, 8)) == "4 años y 3 meses"
    assert ae.meses_de_antiguedad(emp, date(2026, 11, 8)) == 51


def test_cp08_baja_no_crece_con_cortes_posteriores():
    """CP-08: con corte posterior a la baja la antigüedad no cambia."""
    emp = _baja_2023()
    assert ae.calcular_antiguedad(emp, date(2023, 6, 15)) == "4 años y 3 meses"
    assert ae.calcular_antiguedad(emp, date(2030, 1, 1)) == "4 años y 3 meses"


# ---------------------------------------------------------------- C-09

def test_cp09_baja_con_corte_anterior_usa_el_corte():
    """CP-09: baja 2023-06-15, corte 2021-03-04 -> «2 años y 0 meses»."""
    emp = _baja_2023()
    assert ae.calcular_antiguedad(emp, date(2021, 3, 4)) == "2 años y 0 meses"
    assert ae.meses_de_antiguedad(emp, date(2021, 3, 4)) == 24


# ---------------------------------------------------------------- C-10

def test_cp10_corte_futuro_permitido():
    """CP-10: corte futuro 2030-03-04 -> «11 años y 0 meses» sin error."""
    emp = _emp(ingreso=date(2019, 3, 4))
    assert ae.calcular_antiguedad(emp, date(2030, 3, 4)) == "11 años y 0 meses"
    assert ae.meses_de_antiguedad(emp, date(2030, 3, 4)) == 132
    assert ae.meses_completos(date(2019, 3, 4), date(2030, 3, 4)) == 132


# ---------------------------------------------------------------- C-11

def test_cp11_ingreso_posterior_al_corte_calcular_antiguedad():
    """CP-11: ingreso 2027-01-01 con corte 2026-11-08 lanza ValueError con mensaje exacto."""
    emp = _emp(ingreso=date(2027, 1, 1))
    with pytest.raises(ValueError) as exc:
        ae.calcular_antiguedad(emp, date(2026, 11, 8))
    assert str(exc.value) == MENSAJE_ERROR


def test_cp11_ingreso_posterior_al_corte_meses_de_antiguedad():
    """CP-11: meses_de_antiguedad lanza ValueError con el mensaje exacto."""
    emp = _emp(ingreso=date(2027, 1, 1))
    with pytest.raises(ValueError) as exc:
        ae.meses_de_antiguedad(emp, date(2026, 11, 8))
    assert str(exc.value) == MENSAJE_ERROR


def test_cp11_ingreso_posterior_al_corte_meses_completos():
    """CP-11: meses_completos lanza ValueError con el mensaje exacto si desde > hasta."""
    with pytest.raises(ValueError) as exc:
        ae.meses_completos(date(2027, 1, 1), date(2026, 11, 8))
    assert str(exc.value) == MENSAJE_ERROR


def test_cp11_un_dia_posterior_tambien_es_error():
    """CP-11: ingreso un día después del corte es error; el mismo día no."""
    with pytest.raises(ValueError) as exc:
        ae.calcular_antiguedad(_emp(ingreso=date(2026, 11, 9)), date(2026, 11, 8))
    assert str(exc.value) == MENSAJE_ERROR
    assert (
        ae.calcular_antiguedad(_emp(ingreso=date(2026, 11, 8)), date(2026, 11, 8))
        == "0 años y 0 meses"
    )


# ---------------------------------------------------------------- C-12

def test_cp12_lista_solo_activos():
    """CP-12: EMP-0002 (baja) no aparece aunque tenga la mayor antigüedad bruta."""
    empleados = [
        _emp("EMP-0001", date(2015, 6, 10), nombre="Ana"),
        _emp("EMP-0002", date(2010, 1, 1), "baja", date(2020, 1, 1), nombre="Beto"),
        _emp("EMP-0003", date(2019, 3, 4), nombre="Carla"),
    ]
    resultado = ae.lista_reconocimientos(empleados, date(2026, 11, 8))
    assert [fila[0] for fila in resultado] == ["EMP-0001", "EMP-0003"]
    assert "EMP-0002" not in [fila[0] for fila in resultado]


def test_cp12_lista_vacia_o_sin_activos():
    """CP-12: sin empleados activos la lista es vacía."""
    assert ae.lista_reconocimientos([], date(2026, 11, 8)) == []
    solo_baja = [_emp("EMP-0002", date(2010, 1, 1), "baja", date(2020, 1, 1))]
    assert ae.lista_reconocimientos(solo_baja, date(2026, 11, 8)) == []


# ---------------------------------------------------------------- C-13

def test_cp13_orden_por_antiguedad_y_numero():
    """CP-13: orden EMP-0001, EMP-0003, EMP-0004 con sus antigüedades en texto."""
    empleados = [
        _emp("EMP-0004", date(2019, 3, 4), nombre="Diego"),
        _emp("EMP-0003", date(2019, 3, 4), nombre="Carla"),
        _emp("EMP-0001", date(2015, 6, 10), nombre="Ana"),
    ]
    resultado = ae.lista_reconocimientos(empleados, date(2026, 11, 8))
    assert len(resultado) == 3
    assert [fila[0] for fila in resultado] == ["EMP-0001", "EMP-0003", "EMP-0004"]
    assert [fila[2] for fila in resultado] == [
        "11 años y 4 meses",
        "7 años y 8 meses",
        "7 años y 8 meses",
    ]
    assert [fila[1] for fila in resultado] == ["Ana", "Carla", "Diego"]


def test_cp13_orden_no_depende_del_orden_de_entrada():
    """CP-13: mayor antigüedad primero aunque tenga número mayor; empate por número."""
    empleados = [
        _emp("EMP-0001", date(2024, 1, 1), nombre="Nuevo"),
        _emp("EMP-0009", date(2010, 5, 5), nombre="Veterano"),
        _emp("EMP-0003", date(2019, 3, 4), nombre="Medio B"),
        _emp("EMP-0002", date(2019, 3, 4), nombre="Medio A"),
    ]
    resultado = ae.lista_reconocimientos(empleados, date(2026, 11, 8))
    assert [fila[0] for fila in resultado] == [
        "EMP-0009", "EMP-0002", "EMP-0003", "EMP-0001",
    ]


def test_cp13_empate_se_decide_por_meses_completos_no_por_fecha():
    """CP-13: mismos meses completos con distintos días de ingreso empatan: manda el número.

    Con corte 2026-11-08, los ingresos 2019-03-04 y 2019-03-08 (día <= 8) dan
    ambos 92 meses completos, así que el empate se resuelve por número ascendente.
    """
    empleados = [
        _emp("EMP-0002", date(2019, 3, 4)),
        _emp("EMP-0001", date(2019, 3, 8)),
    ]
    corte = date(2026, 11, 8)
    assert ae.meses_de_antiguedad(empleados[0], corte) == 92
    assert ae.meses_de_antiguedad(empleados[1], corte) == 92
    resultado = ae.lista_reconocimientos(empleados, corte)
    assert [fila[0] for fila in resultado] == ["EMP-0001", "EMP-0002"]
    assert [fila[2] for fila in resultado] == ["7 años y 8 meses", "7 años y 8 meses"]


def test_cp13_dia_de_ingreso_posterior_resta_un_mes_y_no_empata():
    """CP-13: ingreso 2019-03-20 con corte 2026-11-08 da 91 meses (el 92 se completa el 20).

    EMP-0002 (92 meses) va antes que EMP-0001 (91 meses) aunque su número sea mayor.
    """
    empleados = [
        _emp("EMP-0001", date(2019, 3, 20)),
        _emp("EMP-0002", date(2019, 3, 4)),
    ]
    resultado = ae.lista_reconocimientos(empleados, date(2026, 11, 8))
    assert [fila[0] for fila in resultado] == ["EMP-0002", "EMP-0001"]
    assert [fila[2] for fila in resultado] == ["7 años y 8 meses", "7 años y 7 meses"]


def test_cp13_lista_con_baja_mezclada_ejemplo_completo():
    """CP-13: ejemplo completo con un empleado de baja excluido y orden correcto."""
    empleados = [
        _emp("EMP-0004", date(2019, 3, 4)),
        _emp("EMP-0002", date(2010, 1, 1), "baja", date(2020, 1, 1)),
        _emp("EMP-0003", date(2019, 3, 4)),
        _emp("EMP-0001", date(2015, 6, 10)),
    ]
    resultado = ae.lista_reconocimientos(empleados, date(2026, 11, 8))
    assert [(fila[0], fila[2]) for fila in resultado] == [
        ("EMP-0001", "11 años y 4 meses"),
        ("EMP-0003", "7 años y 8 meses"),
        ("EMP-0004", "7 años y 8 meses"),
    ]
