"""Pruebas de los endpoints de evaluación de proyectos."""

import pytest
from fastapi.testclient import TestClient

from api import app
from motor.narrativa import contexto_proyecto
from motor.proyectos import Proyecto, evaluar_proyecto


@pytest.fixture(scope="module")
def cliente():
    return TestClient(app)


@pytest.fixture
def espiga() -> dict:
    """El taller de la sesion 6, tal como lo enviaria la interfaz."""
    return {
        "nombre": "Panaderia Espiga S.A.",
        "inversion": 1500,
        "flujos": [400, 500, 600, 700],
        "tasa_descuento": 0.10,
        "plazo_exigido": 3,
        "unidad": "millones",
    }


# ------------------------------------------------------------------- evaluar


def test_evaluar_devuelve_las_cifras_de_clase(cliente, espiga):
    r = cliente.post("/api/proyecto/evaluar", json=espiga)
    assert r.status_code == 200
    metricas = {m["codigo"]: m["valor"] for m in r.json()["metricas"]}
    assert metricas["vpn"] == pytest.approx(206, abs=1)
    assert metricas["indice_rentabilidad"] == pytest.approx(1.14, abs=0.01)
    assert metricas["payback_descontado"] == pytest.approx(3.57, abs=0.01)


def test_evaluar_trae_semaforo_y_veredicto(cliente, espiga):
    cuerpo = cliente.post("/api/proyecto/evaluar", json=espiga).json()
    assert cuerpo["semaforo"] == "amarillo"
    assert cuerpo["veredicto"] == "viable con reparos"
    assert cuerpo["recomendacion"]


def test_evaluar_trae_escenarios_y_punto_de_quiebre(cliente, espiga):
    cuerpo = cliente.post("/api/proyecto/evaluar", json=espiga).json()
    assert len(cuerpo["escenarios"]) == 3
    assert cuerpo["punto_de_quiebre"]["caida_tolerada"] > 0


def test_evaluar_trae_la_tabla_auditable(cliente, espiga):
    """El usuario tiene que poder cuadrar cada renglon contra su Excel."""
    filas = cliente.post("/api/proyecto/evaluar", json=espiga).json()["tabla_descuento"]
    assert len(filas) == 5
    assert filas[1]["valor_presente"] == pytest.approx(363.64, abs=0.01)


def test_evaluar_rechaza_inversion_negativa(cliente, espiga):
    espiga["inversion"] = -1500
    assert cliente.post("/api/proyecto/evaluar", json=espiga).status_code == 422


def test_evaluar_rechaza_proyecto_sin_flujos(cliente, espiga):
    espiga["flujos"] = []
    assert cliente.post("/api/proyecto/evaluar", json=espiga).status_code == 422


def test_evaluar_rechaza_tasa_absurda(cliente, espiga):
    espiga["tasa_descuento"] = -2
    assert cliente.post("/api/proyecto/evaluar", json=espiga).status_code == 422


def test_evaluar_acepta_proyecto_sin_plazo_exigido(cliente, espiga):
    espiga.pop("plazo_exigido")
    r = cliente.post("/api/proyecto/evaluar", json=espiga)
    assert r.status_code == 200
    assert r.json()["semaforo"] == "verde"


# ---------------------------------------------------------------------- WACC


def test_wacc_pondera(cliente):
    r = cliente.post("/api/proyecto/wacc", json={
        "patrimonio": 600, "deuda": 400,
        "costo_patrimonio": 0.18, "costo_deuda": 0.12, "tasa_impuestos": 0.35,
    })
    assert r.status_code == 200
    assert r.json()["valor"] == pytest.approx(0.1392, abs=0.0001)


def test_wacc_reporta_faltantes_en_vez_de_suponer(cliente):
    r = cliente.post("/api/proyecto/wacc", json={"patrimonio": 600})
    assert r.status_code == 200
    assert r.json()["valor"] is None
    assert "deuda" in r.json()["faltantes"]


# ------------------------------------------------------------- flujo mensual


def _meses(entradas, salidas):
    nombres = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
               "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    return [{"mes": n, "entradas": {"recaudos": entradas},
             "salidas": {"gastos": salidas}} for n in nombres]


def test_flujo_mensual_encadena_saldos(cliente):
    r = cliente.post("/api/proyecto/flujo-mensual",
                     json={"saldo_inicial": 150, "meses": _meses(420, 407)})
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["meses"][0]["saldo_final"] == pytest.approx(163)
    assert cuerpo["hay_deficit"] is False


def test_flujo_mensual_detecta_el_descalce(cliente):
    meses = _meses(420, 407)
    meses[2]["salidas"]["capex"] = 600
    r = cliente.post("/api/proyecto/flujo-mensual",
                     json={"saldo_inicial": 150, "meses": meses})
    cuerpo = r.json()
    assert cuerpo["hay_deficit"] is True
    assert cuerpo["meses_en_deficit"][0] == "Marzo"


def test_flujo_mensual_rechaza_meses_mal_formados(cliente):
    r = cliente.post("/api/proyecto/flujo-mensual", json={
        "saldo_inicial": 0,
        "meses": [{"mes": "Enero", "entradas": {"x": "no es un número"}}],
    })
    assert r.status_code == 422


# ------------------------------------------------------------------ contexto


def test_el_contexto_de_la_ia_no_inventa_cifras(espiga):
    """Transparencia: el modelo solo ve números que el motor ya cálculo."""
    evaluacion = evaluar_proyecto(Proyecto(**espiga))
    contexto = contexto_proyecto(evaluacion)
    assert "VEREDICTO DEL MOTOR: VIABLE CON REPAROS" in contexto
    assert "Payback descontado" in contexto
    assert "3.57 años" in contexto
    assert "ESCENARIOS:" in contexto


def test_el_contexto_incluye_los_reparos(espiga):
    evaluacion = evaluar_proyecto(Proyecto(**espiga))
    assert "REPAROS:" in contexto_proyecto(evaluacion)


def test_narrar_proyecto_sin_ia_devuelve_la_evaluacion_igual(cliente, espiga, monkeypatch):
    """Sin clave de IA la evaluación numerica sigue sirviendo."""
    monkeypatch.setattr("motor.narrativa.disponible", lambda: False)
    r = cliente.post("/api/proyecto/narrar", json=espiga)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["disponible"] is False
    assert cuerpo["evaluacion"]["veredicto"] == "viable con reparos"
