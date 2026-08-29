"""Pruebas de la API HTTP."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api import app

CASO = Path(__file__).resolve().parents[2] / "casos" / "comercial_andina.json"


@pytest.fixture(scope="module")
def cliente():
    return TestClient(app)


@pytest.fixture(scope="module")
def datos():
    with open(CASO, encoding="utf-8") as fh:
        return json.load(fh)


def test_salud(cliente):
    r = cliente.get("/api/salud")
    assert r.status_code == 200
    assert r.json()["estado"] == "ok"


def test_lista_de_casos(cliente):
    casos = cliente.get("/api/casos").json()
    assert any(c["id"] == "comercial_andina" for c in casos)


def test_caso_inexistente_da_404(cliente):
    assert cliente.get("/api/casos/no_existe").status_code == 404


def test_analisis_de_caso_guardado(cliente):
    r = cliente.get("/api/casos/comercial_andina/analisis")
    assert r.status_code == 200
    assert r.json()["validacion"]["semaforo"] == "rojo"


def test_post_analizar_devuelve_estructura_completa(cliente, datos):
    r = cliente.post("/api/analizar", json=datos)
    assert r.status_code == 200
    cuerpo = r.json()
    for clave in ("validacion", "indicadores", "vertical", "horizontal",
                  "dupont", "puente_caja", "alertas", "recomendaciones"):
        assert clave in cuerpo, f"Falta '{clave}' en la respuesta"
    assert len(cuerpo["indicadores"]) >= 20
    assert len(cuerpo["alertas"]) > 0


def test_todo_indicador_serializa_su_trazabilidad(cliente, datos):
    """El modo docente del frontend depende de estos campos."""
    for i in cliente.post("/api/analizar", json=datos).json()["indicadores"]:
        assert i["formula"] and i["insumos"] and "disponible" in i


def test_periodos_inconsistentes_dan_422(cliente):
    malo = {"periodos": ["2023", "2024"], "balance": {"efectivo": [100]}}
    assert cliente.post("/api/analizar", json=malo).status_code == 422


def test_escenario_mejorar_cartera_vuelve_positivo_el_flujo(cliente, datos):
    """Simulacion: si la cartera baja, el flujo de caja libre deja de ser negativo."""
    base = cliente.post("/api/analizar", json=datos).json()
    assert base["puente_caja"]["flujo_caja_libre_aprox"] < 0

    mejorado = json.loads(json.dumps(datos))
    mejorado["balance"]["cuentas_por_cobrar"][1] = 1200
    nuevo = cliente.post("/api/analizar", json=mejorado).json()

    assert nuevo["puente_caja"]["flujo_caja_libre_aprox"] > 0
    assert len(nuevo["alertas"]) < len(base["alertas"])


def test_frontend_se_sirve(cliente):
    r = cliente.get("/")
    assert r.status_code == 200
    assert "Diagn" in r.text
