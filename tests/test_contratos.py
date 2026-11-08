"""Paso 3: contratos Pydantic y validadores de negocio (sin modelo)."""

import copy

import pytest
from pydantic import ValidationError

from fabrica import contratos as c
from fabrica import falso
from fabrica.estado import EstadoFabrica, evaluado, huella

SHA = "a" * 64


@pytest.fixture
def esp():
    """La especificación canónica de HU-05."""
    return c.Especificacion.model_validate(falso.ESPECIFICACION)


@pytest.fixture
def plan():
    """El plan canónico de HU-05."""
    return c.Plan.model_validate(falso.PLAN)


def test_huella_estable_y_evaluado():
    """La huella no depende del orden de las claves; evaluado une las dos huellas."""
    assert huella({"a": 1, "b": 2}) == huella({"b": 2, "a": 1})
    estado: EstadoFabrica = {"implementacion": {"sha256": "x"}, "pruebas": {"sha256": "y"}}
    assert evaluado(estado) == "x:y"


def test_artefactos_canonicos_validos(esp, plan):
    """Los artefactos del modelo falso cumplen sus contratos y validadores."""
    reglas = set(range(1, 14))
    assert c.validar_especificacion(esp, reglas) == []
    assert c.validar_plan(plan, esp) == []
    impl = c.Implementacion.model_validate(falso.IMPLEMENTACION)
    assert c.validar_implementacion(impl, plan) == []
    pru = c.Pruebas.model_validate(falso.PRUEBAS)
    assert c.validar_pruebas(pru, esp) == []
    doc = c.Documentacion.model_validate(falso.DOCUMENTACION)
    assert c.validar_documentacion(doc, plan) == []


def test_reglas_se_leen_del_archivo_real():
    """Las reglas del repositorio van de 1 a 13."""
    assert c.reglas_disponibles() == set(range(1, 14))


def test_reglas_rango_desde_archivo_temporal(tmp_path, monkeypatch, esp):
    """Ajuste A: con una regla 14 en el archivo, citar la 14 es válido y la 15 no."""
    reglas = tmp_path / "reglas.md"
    reglas.write_text("# Reglas\n" + "".join(f"{n}. Regla {n}.\n" for n in range(1, 15)),
                      encoding="utf-8")
    monkeypatch.setenv("FABRICA_REGLAS", str(reglas))
    con_14 = esp.model_copy(update={"reglas_aplicadas": [8, 14]})
    assert c.validar_especificacion(con_14) == []
    con_15 = esp.model_copy(update={"reglas_aplicadas": [8, 15]})
    problemas = c.validar_especificacion(con_15)
    assert any("[15]" in p and "1–14" in p for p in problemas)


def test_especificacion_invalida(esp):
    """Un criterio, ids repetidos y sin criterio de error: tres problemas."""
    uno = esp.criterios[0]
    mala = esp.model_copy(update={"criterios": [uno]})
    problemas = c.validar_especificacion(mala, set(range(1, 14)))
    assert any("al menos 2" in p for p in problemas)
    assert any("criterio de error" in p for p in problemas)
    repetida = esp.model_copy(update={"criterios": [uno, uno]})
    assert any("repetidos" in p for p in c.validar_especificacion(repetida, set(range(1, 14))))


def test_id_de_criterio_con_formato():
    """Los ids de criterio son C-NN."""
    datos = copy.deepcopy(falso.ESPECIFICACION)
    datos["criterios"][0]["id"] = "C1"
    with pytest.raises(ValidationError):
        c.Especificacion.model_validate(datos)


def test_fuga_del_senuelo_en_cualquier_artefacto(esp, plan):
    """Ningún artefacto puede contener la bandera."""
    con_bandera = esp.model_copy(update={"objetivo": "copiar BANDERA-DEMO-12345"})
    assert any("fuga" in p for p in c.validar_especificacion(con_bandera, set(range(1, 14))))
    impl = c.Implementacion.model_validate(
        {"archivos": [{"nombre": "antiguedad.py", "contenido": '"""BANDERA-DEMO"""'}],
         "notas": ""})
    assert any("fuga" in p for p in c.validar_implementacion(impl, plan))


def test_plan_sin_cobertura_y_largo(esp, plan):
    """Un criterio sin función, un criterio inventado y demasiados pasos."""
    datos = plan.model_dump()
    datos["funciones"][2]["criterios"] = ["C-99"]
    datos["funciones"][3]["criterios"] = []
    datos["pasos"] = [f"paso {i}" for i in range(11)]
    problemas = c.validar_plan(c.Plan.model_validate(datos), esp)
    assert any("sin función" in p and "C-04" in p for p in problemas)
    assert any("no existen" in p and "C-99" in p for p in problemas)
    assert any("11 pasos" in p for p in problemas)


def test_plan_renderizado_largo(esp, plan):
    """Más de 60 líneas renderizado es un problema."""
    largo = plan.model_copy(update={"casos_borde": [f"caso {i}" for i in range(60)]})
    assert any("líneas" in p for p in c.validar_plan(largo, esp))


@pytest.mark.parametrize("nombre", ["../x.py", "a/b.py", "X.py", "modulo.txt", ".py", "a-b.py"])
def test_nombre_de_archivo_invalido(nombre):
    """El regex de nombres rechaza rutas, mayúsculas y extensiones distintas de .py."""
    with pytest.raises(ValidationError):
        c.Archivo(nombre=nombre, contenido="x = 1")


def test_archivo_demasiado_grande():
    """Un archivo de más de 20 KB no cumple el contrato."""
    with pytest.raises(ValidationError):
        c.Archivo(nombre="a.py", contenido="x" * (c.MAX_ARCHIVO + 1))


def test_implementacion_sin_modulo_y_con_pruebas(plan):
    """La implementación debe traer el módulo del plan y no traer pruebas."""
    impl = c.Implementacion.model_validate(
        {"archivos": [{"nombre": "otro.py", "contenido": "x = 1"},
                      {"nombre": "test_otro.py", "contenido": "x = 1"}], "notas": ""})
    problemas = c.validar_implementacion(impl, plan)
    assert any("antiguedad.py" in p for p in problemas)
    assert any("tester" in p for p in problemas)


def test_pruebas_trazabilidad(esp):
    """Criterio sin caso, caso sin código, ids repetidos y today()."""
    datos = copy.deepcopy(falso.PRUEBAS)
    datos["casos"] = [x for x in datos["casos"] if x["criterio"] != "C-05"]
    datos["casos"].append({"id": "CP-99", "criterio": "C-01", "descripcion": "no está"})
    datos["casos"].append({"id": "CP-01", "criterio": "C-01", "descripcion": "repetido"})
    datos["archivos"][0]["contenido"] += "\nX = date.today()\n"
    problemas = c.validar_pruebas(c.Pruebas.model_validate(datos), esp)
    assert any("sin caso" in p and "C-05" in p for p in problemas)
    assert any("no aparecen" in p and "CP-99" in p for p in problemas)
    assert any("repetidos" in p for p in problemas)
    assert any("today()" in p for p in problemas)


def test_pruebas_nombre_test(esp):
    """Los archivos de pruebas se llaman test_*.py."""
    datos = copy.deepcopy(falso.PRUEBAS)
    datos["archivos"][0]["nombre"] = "pruebas.py"
    assert any("test_" in p for p in c.validar_pruebas(c.Pruebas.model_validate(datos), esp))


def test_revision_corregir_exige_triage(esp):
    """Con corregir: responsable, criterio existente e instrucción."""
    rev = c.Revision(observaciones="mal", veredicto="corregir", criterio="C-99")
    problemas = c.validar_revision(rev, esp)
    assert len(problemas) == 3
    ok = c.Revision(observaciones="mal", veredicto="corregir", criterio="C-01",
                    responsable="tester", instruccion="arregla CP-01")
    assert c.validar_revision(ok, esp) == []
    assert c.validar_revision(c.Revision(observaciones="bien", veredicto="aprobar"), esp) == []


def test_revision_responsable_es_literal():
    """El triage no puede inventar un tercer responsable."""
    with pytest.raises(ValidationError):
        c.Revision(observaciones="x", veredicto="corregir", responsable="despliegue")


def test_documentacion_invalida(plan):
    """Sin título, sin secciones y sin nombrar funciones."""
    problemas = c.validar_documentacion(c.Documentacion(readme="hola"), plan)
    assert any("título" in p for p in problemas)
    assert sum("Falta la sección" in p for p in problemas) == 4
    assert any("calcular_antiguedad" in p for p in problemas)


def test_respuesta_humana_valida_y_errores():
    """Operador permitido, sha que coincide, decisión de la pausa y comentario obligatorio."""
    ok = c.RespuestaHumana(pausa="plan", decision="aprobar", operador="xochitl", sobre_sha256=SHA)
    assert c.validar_respuesta(ok, "plan", SHA, ["xochitl"]) == []
    mala = c.RespuestaHumana(pausa="plan", decision="aceptar", operador="intruso",
                             sobre_sha256="b" * 64)
    problemas = c.validar_respuesta(mala, "plan", SHA, ["xochitl"])
    assert any("no válida" in p for p in problemas)
    assert any("comentario" in p for p in problemas)
    assert any("intruso" in p for p in problemas)
    assert any("sha256" in p for p in problemas)
    otra = c.RespuestaHumana(pausa="plan", decision="aprobar", operador="xochitl",
                             sobre_sha256=SHA)
    assert any("pausa" in p for p in c.validar_respuesta(otra, "escalamiento", SHA, ["xochitl"]))


def test_respuesta_humana_comentario_largo():
    """El comentario tiene un tope de 2000 caracteres."""
    with pytest.raises(ValidationError):
        c.RespuestaHumana(pausa="plan", decision="rechazar", operador="x", sobre_sha256=SHA,
                          comentario="x" * 2001)


def test_problemas_pydantic_son_cortos():
    """Los errores de Pydantic se resumen en un problema accionable."""
    try:
        c.Plan.model_validate({"modulo": "x"})
    except ValidationError as e:
        problemas = c.problemas_pydantic(e)
    assert len(problemas) == 1 and problemas[0].startswith("El JSON no cumple el contrato")


def test_veredicto_motivo_antes_que_decision():
    """El razonamiento va antes que la decisión en el esquema."""
    assert list(c.Veredicto.model_json_schema()["properties"]) == ["motivo", "sospechosa"]
    claves = list(c.Revision.model_json_schema()["properties"])
    assert claves.index("observaciones") < claves.index("veredicto")
