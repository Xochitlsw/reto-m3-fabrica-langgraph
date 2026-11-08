"""Paso 11 (ajuste B): el nodo fin copia la evidencia solo en las corridas con el modelo real."""

import copy

from fabrica import falso
from fabrica.grafo import nodo_fin
from fabrica.seguridad import log


def _estado(modelo: str) -> dict:
    return {
        "hilo": "h-ev", "hu": "HU-05", "modelo": modelo,
        "estado_final": "LISTA", "motivo_final": "flujo completo",
        "especificacion": copy.deepcopy(falso.ESPECIFICACION), "plan": copy.deepcopy(falso.PLAN),
        "implementacion": copy.deepcopy(falso.IMPLEMENTACION),
        "pruebas": copy.deepcopy(falso.PRUEBAS),
        "documentacion": copy.deepcopy(falso.DOCUMENTACION),
        "llamadas": [{"agente": "especificador", "intento": 1, "costo_usd": 0.02, "turnos": 1,
                      "tokens": {"input_tokens": 100}, "segundos": 3.1}],
        "costo_usd": 0.02, "bitacora": ["[guardian] OK"],
    }


def test_real_copia_los_cinco_elementos(rutas_temporales):
    """reporte.md, llamadas.json, codigo/ + pruebas/ + README.md y seguridad.jsonl."""
    log.registrar("aprobacion", hilo="h-ev", operador="xochitl")
    update = nodo_fin(_estado("real"))
    destino = rutas_temporales / "evidencia" / "h-ev"
    assert (destino / "reporte.md").read_text(encoding="utf-8").count("LISTA") >= 1
    assert '"especificador"' in (destino / "llamadas.json").read_text(encoding="utf-8")
    assert (destino / "codigo" / "antiguedad.py").exists()
    assert (destino / "pruebas" / "test_antiguedad.py").exists()
    assert (destino / "README.md").exists()
    assert '"aprobacion"' in (destino / "seguridad.jsonl").read_text(encoding="utf-8")
    assert any("evidencia copiada" in x for x in update["bitacora"])


def test_falso_no_copia(rutas_temporales):
    """Las corridas con el falso no ensucian la evidencia."""
    nodo_fin(_estado("falso:feliz"))
    assert not (rutas_temporales / "evidencia").exists()
    assert (rutas_temporales / "salida" / "h-ev" / "reporte.md").exists()


def test_bloqueada_desde_el_guardian(rutas_temporales):
    """Si llega sin estado final (desde guardian o filtro), fin la marca BLOQUEADA."""
    estado = {"hilo": "b", "modelo": "real",
              "seguridad": {"bloqueada": True, "capa": "reglas", "motivos": ["fuera de ruta"]}}
    update = nodo_fin(estado)
    assert update["estado_final"] == "BLOQUEADA POR SEGURIDAD"
    assert "fuera de ruta" in update["motivo_final"]
    assert (rutas_temporales / "evidencia" / "b" / "reporte.md").exists()


def test_la_bandera_nunca_sale(rutas_temporales):
    """Si la bandera del señuelo apareciera en la bitácora, se redacta al escribir."""
    estado = _estado("real")
    estado["bitacora"] = ["[filtro] contenido BANDERA-DEMO-12345"]
    nodo_fin(estado)
    for carpeta in ("salida/h-ev", "evidencia/h-ev"):
        texto = (rutas_temporales / carpeta / "reporte.md").read_text(encoding="utf-8")
        assert "BANDERA-DEMO" not in texto and "REDACTADO" in texto
