# antiguedad_empleados

Módulo de Python (HU-05) para que Recursos Humanos obtenga la antigüedad de un empleado en años y meses completos, calculada a una fecha de corte (por omisión, hoy). También genera la lista de empleados activos ordenada por antigüedad, para preparar los reconocimientos por aniversario.

El módulo no accede a bases de datos: las funciones reciben los empleados ya cargados.

## Uso

Funciones públicas:

| Función | Qué hace |
|---|---|
| `hoy() -> date` | Devuelve `date.today()`. Es la fecha de corte por omisión y se evalúa en tiempo de ejecución, no al definir las funciones. |
| `meses_completos(desde: date, hasta: date) -> int` | Meses completos entre dos fechas. Si `desde == hasta` devuelve 0. Lanza `ValueError` si `desde > hasta`. |
| `formatear_antiguedad(anios: int, meses: int) -> str` | Da el texto «N años y M meses». Usa singular con 1 («1 año», «1 mes») y muestra siempre las dos partes, aunque valgan 0. |
| `meses_de_antiguedad(empleado: Empleado, fecha_corte: date \| None = None) -> int` | Antigüedad total en meses completos. Si `fecha_corte` es `None`, usa `hoy()`. |
| `calcular_antiguedad(empleado: Empleado, fecha_corte: date \| None = None) -> str` | Antigüedad como texto, por ejemplo «7 años y 8 meses». Convierte los meses con `divmod(meses, 12)` y los formatea con `formatear_antiguedad`. |
| `lista_reconocimientos(empleados: list[Empleado], fecha_corte: date \| None = None) -> list[tuple[str, str, str]]` | Lista solo a los empleados activos, como tuplas `(numero, nombre, antigüedad en texto)`. |

### Reglas de cálculo

- **Meses completos:** los días sobrantes no cuentan.
- **Cuándo se completa un mes:** el mismo día del mes siguiente. Si ese día no existe en el mes, se completa el último día de ese mes. Ejemplo: con ingreso el 2026-01-31, el primer mes se completa el 2026-02-28.
- **Fecha de corte omitida:** se usa la fecha de hoy.
- **Fecha de corte futura:** se permite y no da error.
- **Empleado dado de baja** (estado «baja»): la antigüedad se cuenta hasta `min(fecha_baja, fecha_corte)`. No crece con cortes posteriores a la baja.
- **Ingreso posterior al corte:** `meses_completos`, `meses_de_antiguedad` y `calcular_antiguedad` lanzan `ValueError("La fecha de ingreso no puede ser posterior a la fecha de corte")`. Ingreso igual al corte no es error y da «0 años y 0 meses».
- **Lista para reconocimientos:** se excluye a los empleados de baja. El orden es de mayor a menor número de meses completos. En empate de meses, se ordena por número de empleado ascendente. El orden se calcula con los meses, no con el texto. Si `fecha_corte` es `None`, `hoy()` se evalúa una sola vez para toda la lista.

## Ejemplos

Los valores de entrada y salida son los de la especificación. `empleado` es un empleado con los datos que se indican en cada caso.

```python
from datetime import date
from antiguedad_empleados import (
    calcular_antiguedad, meses_de_antiguedad, meses_completos,
    formatear_antiguedad, lista_reconocimientos, hoy,
)

# Empleado activo, ingreso 2019-03-04
calcular_antiguedad(empleado, date(2026, 11, 8))   # "7 años y 8 meses"
meses_de_antiguedad(empleado, date(2026, 11, 8))   # 92
calcular_antiguedad(empleado)                      # sin corte usa hoy(); con hoy = 2026-11-08: "7 años y 8 meses"
calcular_antiguedad(empleado, date(2030, 3, 4))    # "11 años y 0 meses" (corte futuro, sin error)

# Los días sobrantes no cuentan (ingreso 2020-01-15)
calcular_antiguedad(empleado, date(2026, 11, 14))  # "6 años y 9 meses"

# Meses completos entre fechas
meses_completos(date(2026, 1, 15), date(2026, 2, 15))  # 1
meses_completos(date(2026, 1, 15), date(2026, 2, 14))  # 0
meses_completos(date(2026, 1, 31), date(2026, 2, 28))  # 1
meses_completos(date(2026, 1, 31), date(2026, 2, 27))  # 0
meses_completos(date(2026, 1, 31), date(2026, 3, 30))  # 1 (el segundo mes se completa el 2026-03-31)

# Singular y las dos partes siempre
formatear_antiguedad(1, 1)   # "1 año y 1 mes"
formatear_antiguedad(1, 0)   # "1 año y 0 meses"
formatear_antiguedad(0, 1)   # "0 años y 1 mes"
formatear_antiguedad(0, 0)   # "0 años y 0 meses"
# Con corte 2026-11-08, ingresos 2025-10-08, 2025-11-08, 2026-10-08 y 2026-11-08
# dan: "1 año y 1 mes", "1 año y 0 meses", "0 años y 1 mes" y "0 años y 0 meses"

# Empleado en baja: ingreso 2019-03-04, baja 2023-06-15
calcular_antiguedad(empleado_baja, date(2026, 11, 8))  # "4 años y 3 meses" (hasta la baja)
calcular_antiguedad(empleado_baja, date(2021, 3, 4))   # "2 años y 0 meses" (hasta el corte)

# Ingreso posterior al corte (ingreso 2027-01-01)
calcular_antiguedad(empleado, date(2026, 11, 8))
# ValueError: La fecha de ingreso no puede ser posterior a la fecha de corte
```

Lista para reconocimientos con corte 2026-11-08. Los empleados son EMP-0004 (activo, ingreso 2019-03-04), EMP-0002 (baja, ingreso 2010-01-01, baja 2020-01-01), EMP-0003 (activo, ingreso 2019-03-04) y EMP-0001 (activo, ingreso 2015-06-10):

```python
lista_reconocimientos(empleados, date(2026, 11, 8))
# [
#   ("EMP-0001", <nombre>, "11 años y 4 meses"),
#   ("EMP-0003", <nombre>, "7 años y 8 meses"),
#   ("EMP-0004", <nombre>, "7 años y 8 meses"),
# ]
# EMP-0002 queda fuera por estar de baja, aunque tenga la mayor antigüedad bruta.
# EMP-0003 y EMP-0004 empatan y se ordenan por número ascendente.
```

## Pruebas

- Resultado: 33 pruebas aprobadas y 0 fallidas, sin problemas estáticos. La revisión aprobó el módulo.
- Hay casos CP-01 a CP-13, uno por cada criterio C-01 a C-13 de la especificación, con valores exactos.
- También hay bordes adicionales: 29 de febrero, año bisiesto, meses de 30 días, empate por meses completos (incluidos ingresos con días distintos), lista vacía y lista sin activos.
- Para ejecutarlas, usa el corredor de pruebas del proyecto, por ejemplo `python -m pytest` desde la carpeta del módulo.
- La prueba de C-02 (fecha de corte omitida) no puede fijar la fecha de hoy sin sustituir `hoy()`. Por eso compara el resultado sin corte contra el resultado con `hoy()` pasada de forma explícita como `fecha_corte`.

## Limitaciones

- **Lista con un ingreso posterior al corte (pendiente de confirmar):** la especificación no dice qué pasa en `lista_reconocimientos` si un empleado activo tiene ingreso posterior a la fecha de corte. Se implementó la suposición del plan: se lanza el `ValueError` para toda la lista, y no se omite a ese empleado. Debe confirmarlo quien aprueba.
- **Contenido de cada elemento de la lista:** la especificación dejaba abierto si el elemento llevaba solo al empleado o también su antigüedad. El módulo devuelve la tupla `(numero, nombre, antigüedad en texto)`.
- **Prueba de C-02:** no verifica una fecha fija de «hoy». Compara contra `hoy()` explícita (ver Pruebas).
- **Fuera de alcance:**
  - Registrar, editar o dar de baja empleados, y sus validaciones.
  - Inicio de sesión o control de acceso.
  - HTTP, códigos de estado y pantallas.
  - Envío de notificaciones o generación de documentos de reconocimiento.
  - Persistencia o consulta en base de datos: las funciones reciben los datos ya cargados.
- No hay observaciones adicionales de la persona que aprobó.
