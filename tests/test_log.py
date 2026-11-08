"""Paso 5: el log de seguridad."""

import pytest

from fabrica.seguridad import log


def test_linea_con_claves_obligatorias():
    """Cada línea trae ts, evento, hilo, hu, capa, nodo y detalle."""
    linea = log.registrar("bloqueo", hilo="h1", hu="HU-99", capa="reglas", nodo="guardian",
                          detalle="ruta fuera de historias/")
    assert all(clave in linea for clave in log.CLAVES)
    assert log.leer() == [linea]


def test_detalle_recortado_a_300():
    """El detalle se recorta: nunca guarda la historia completa."""
    linea = log.registrar("alerta", detalle="x" * 1000)
    assert len(linea["detalle"]) == log.MAX_DETALLE


def test_extra_operador_y_sha():
    """Las decisiones humanas guardan operador, usuario del sistema y sha256."""
    linea = log.registrar("aprobacion", hilo="h", operador="xochitl", usuario_so=log.usuario_so(),
                          sha256="a" * 64, opcional=None)
    assert linea["operador"] == "xochitl" and linea["sha256"] == "a" * 64
    assert "opcional" not in linea and linea["usuario_so"]


def test_todos_los_eventos_de_la_seccion5():
    """Los 10 eventos de la sección 5 se aceptan y escriben con las claves obligatorias."""
    esperados = {
        "bloqueo", "alerta", "salida_rechazada", "sandbox", "aprobacion", "rechazo",
        "aclaracion", "escalamiento", "defensas_desactivadas", "respuesta_rechazada",
    }
    assert set(log.EVENTOS) == esperados
    for evento in log.EVENTOS:
        linea = log.registrar(evento, hilo="h", hu="HU-05", capa="reglas", nodo="guardian",
                              detalle="prueba")
        assert all(clave in linea for clave in log.CLAVES)
        assert linea["evento"] == evento
    assert {x["evento"] for x in log.leer("h")} == esperados


def test_evento_desconocido():
    """Un evento fuera de la lista es un error."""
    with pytest.raises(ValueError):
        log.registrar("inventado")


def test_leer_por_hilo():
    """leer() filtra por hilo."""
    log.registrar("sandbox", hilo="a")
    log.registrar("sandbox", hilo="b")
    assert [x["hilo"] for x in log.leer("b")] == ["b"]


def test_leer_sin_archivo(monkeypatch, tmp_path):
    """Sin archivo, el log está vacío."""
    monkeypatch.setenv("FABRICA_LOG", str(tmp_path / "no" / "existe.jsonl"))
    assert log.leer() == []
