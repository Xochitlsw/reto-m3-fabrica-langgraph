"""Revisión estática del código generado, con AST y LISTA BLANCA de imports (no lista negra).

Corre en el implementador, en el tester y otra vez en el sandbox, antes de ejecutar nada. Es la
capa principal contra el código malicioso; el sandbox es la segunda (docs/diseno.md, sección 5).
"""

import ast
import re

from fabrica import config

IMPORTS_IMPLEMENTACION = frozenset({
    "datetime", "calendar", "dataclasses", "typing", "enum", "math", "re", "decimal",
    "functools", "itertools", "collections", "__future__",
})
IMPORTS_PRUEBAS_EXTRA = frozenset({"pytest"})
NOMBRES_PROHIBIDOS = frozenset({
    "eval", "exec", "compile", "__import__", "open", "input", "breakpoint", "globals", "locals",
    "vars", "getattr", "setattr", "delattr",
})
# Atributos que evalúan texto como código o recorren atributos internos, aunque el módulo que los
# expone esté en la lista blanca (fase 3). ``_evaluate`` no empieza con ``__``, así que la regla de
# los dunder no lo cubría; ``get_type_hints``/``ForwardRef`` evalúan anotaciones escritas como
# texto; ``make_dataclass`` compila código con ``exec`` por dentro.
ATRIBUTOS_PROHIBIDOS = frozenset({
    "importorskip", "get_type_hints", "ForwardRef", "evaluate_forward_ref", "_evaluate",
    "make_dataclass", "getattr", "setattr", "delattr",
})
DUNDER_PERMITIDOS = frozenset({"__name__", "__doc__"})
CADENAS_PROHIBIDAS = ("secretos", ".env")
NOMBRE_ARCHIVO = re.compile(r"^[a-z_][a-z0-9_]*\.py$")
MAX_BYTES = 20_000
MAX_LINEAS = 600


def _revisar_archivo(nombre: str, contenido: str, permitidos: frozenset[str]) -> list[str]:
    """Problemas de un archivo; vacío si es aceptable."""
    problemas: list[str] = []
    if not NOMBRE_ARCHIVO.match(nombre) or nombre == "conftest.py":
        return [f"{nombre}: nombre de archivo no permitido."]
    if len(contenido.encode("utf-8")) > MAX_BYTES or contenido.count("\n") + 1 > MAX_LINEAS:
        problemas.append(f"{nombre}: pasa de {MAX_BYTES} bytes o de {MAX_LINEAS} líneas.")
    if config.BANDERA in contenido:
        problemas.append(f"{nombre}: contiene {config.BANDERA} (fuga del señuelo).")
    try:
        arbol = ast.parse(contenido, filename=nombre)
    except SyntaxError as e:
        return problemas + [f"{nombre}: sintaxis inválida en la línea {e.lineno}: {e.msg}."]
    for nodo in ast.walk(arbol):
        linea = getattr(nodo, "lineno", "?")
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                raiz = alias.name.split(".")[0]
                if raiz not in permitidos:
                    problemas.append(f"{nombre}:{linea}: import no permitido: {alias.name}.")
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.level:
                problemas.append(f"{nombre}:{linea}: import relativo no permitido.")
            elif (nodo.module or "").split(".")[0] not in permitidos:
                problemas.append(f"{nombre}:{linea}: import no permitido: {nodo.module}.")
            if any(a.name == "*" for a in nodo.names):
                problemas.append(f"{nombre}:{linea}: import * no permitido.")
        elif isinstance(nodo, ast.Name):
            if nodo.id in NOMBRES_PROHIBIDOS:
                problemas.append(f"{nombre}:{linea}: uso prohibido de {nodo.id}.")
            elif nodo.id.startswith("__") and nodo.id not in DUNDER_PERMITIDOS:
                problemas.append(f"{nombre}:{linea}: nombre interno prohibido: {nodo.id}.")
        elif isinstance(nodo, ast.Attribute):
            if nodo.attr.startswith("__") and nodo.attr not in DUNDER_PERMITIDOS:
                problemas.append(f"{nombre}:{linea}: atributo interno prohibido: {nodo.attr}.")
            elif nodo.attr in ATRIBUTOS_PROHIBIDOS:
                problemas.append(f"{nombre}:{linea}: atributo prohibido: {nodo.attr}.")
        elif isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
            bajo = nodo.value.lower()
            for prohibida in CADENAS_PROHIBIDAS:
                if prohibida in bajo:
                    problemas.append(f"{nombre}:{linea}: cadena prohibida: «{prohibida}».")
            # Una cadena con «__» puede esconder una ruta de atributos internos para str.format
            # («{0.__class__.__mro__}»), que no aparece como nodo Attribute en el AST.
            if "__" in nodo.value:
                problemas.append(f"{nombre}:{linea}: cadena con «__» (posible acceso interno).")
    return problemas


def revisar(archivos: list[dict], tipo: str, modulos_propios: list[str] | None = None) -> list[str]:
    """Revisa una lista de ``{nombre, contenido}``.

    ``tipo`` es ``"implementacion"`` o ``"pruebas"``. Los dos pueden importar los módulos propios
    (los archivos de la implementación, sin ``.py``); las pruebas, además, ``pytest``.
    """
    if tipo not in ("implementacion", "pruebas"):
        raise ValueError(f"Tipo desconocido: {tipo}")
    permitidos = IMPORTS_IMPLEMENTACION | frozenset(modulos_propios or ())
    if tipo == "pruebas":
        permitidos = permitidos | IMPORTS_PRUEBAS_EXTRA
    problemas: list[str] = []
    for archivo in archivos:
        problemas += _revisar_archivo(archivo["nombre"], archivo["contenido"], permitidos)
    return problemas
