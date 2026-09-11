"""Punto de equilibrio y apalancamientos, contra los ejemplos de la cartilla.

Los datos son los del modulo 2 (overoles; 20.000 unidades a 15.000). Donde la
cartilla se equivoca -el GAF con dividendos- la prueba fija lo correcto y
documenta la diferencia.
"""

import pytest

from motor.operativo import apalancamiento, punto_equilibrio


# ------------------------------------------------------- punto de equilibrio


def test_los_overoles_de_la_cartilla_dan_96_unidades_y_12_millones():
    """CF 6.000.000; precio 125.000; CVU 12.500.000/200 = 62.500."""
    r = punto_equilibrio(125_000, 62_500, 6_000_000, unidades_programadas=200)
    assert r["punto_equilibrio_unidades"] == pytest.approx(96)
    assert r["punto_equilibrio_pesos"] == pytest.approx(12_000_000)
    assert r["margen_contribucion_unitario"] == 62_500
    assert r["razon_margen_contribucion"] == pytest.approx(0.5)
    assert r["cubre_costos"] is True
    assert r["margen_seguridad"] == pytest.approx((200 - 96) / 200)
    assert r["utilidad_operativa_programada"] == pytest.approx(200 * 62_500 - 6_000_000)
    assert "96" in r["lectura"] and "12.000.000" in r["lectura"]


def test_si_se_programan_menos_unidades_que_el_equilibrio_lo_dice():
    r = punto_equilibrio(125_000, 62_500, 6_000_000, unidades_programadas=50)
    assert r["cubre_costos"] is False
    assert "NO se alcanza" in r["lectura"]


def test_sin_unidades_programadas_no_hay_margen_de_seguridad():
    r = punto_equilibrio(125_000, 62_500, 6_000_000)
    assert "margen_seguridad" not in r
    assert r["punto_equilibrio_unidades"] == pytest.approx(96)


def test_costo_variable_mayor_que_el_precio_no_da_un_numero_negativo():
    """La cartilla advierte que un valor negativo "no es logico": aqui se
    explica en palabras en vez de devolverlo."""
    with pytest.raises(ValueError) as e:
        punto_equilibrio(100, 120, 1000)
    assert "pierde plata" in str(e.value)


def test_precio_cero_o_costos_negativos_se_rechazan():
    with pytest.raises(ValueError):
        punto_equilibrio(0, 10, 100)
    with pytest.raises(ValueError):
        punto_equilibrio(100, -1, 100)


# ------------------------------------------------------------ apalancamiento


def test_el_gao_de_la_cartilla_es_2_38_que_ella_redondea_a_2_4():
    """20.000 unidades a 15.000 con CVU 10.000 y CF 58.000.000."""
    r = apalancamiento(300_000_000, 200_000_000, 58_000_000)
    assert r["margen_contribucion"] == 100_000_000
    assert r["uaii"] == 42_000_000
    assert r["gao"] == pytest.approx(100 / 42)
    assert r["gaf"] == pytest.approx(1.0)      # sin deuda
    assert r["gat"] == pytest.approx(r["gao"])


def test_el_gaf_estandar_con_los_datos_de_la_cartilla_es_1_3125():
    """Deuda de 50 M al 20 % = 10 M de intereses; t = 30 %; dividendos 8 M.
    Estandar: 42/32 = 1,3125. La formula de la cartilla con dividendos da
    42 / (42 - 10 - 8/0,7) = 2,04, no el 1,3 que ella reporta (§8.2)."""
    r = apalancamiento(300_000_000, 200_000_000, 58_000_000,
                       intereses=10_000_000, tasa_impuestos=0.30,
                       dividendos_preferentes=8_000_000)
    assert r["gaf"] == pytest.approx(42 / 32)
    assert r["gaf_cartilla"] == pytest.approx(42 / (42 - 10 - 8 / 0.7))
    assert r["gat"] == pytest.approx((100 / 42) * (42 / 32))
    # el estado de resultados de la cartilla: UAI 32, impuestos 9,6, neta 22,4
    renglones = {f["renglon"]: f["valor"] for f in r["estado_resultados"]}
    assert renglones["= Utilidad antes de impuestos"] == 32_000_000
    assert renglones["− Impuestos"] == pytest.approx(-9_600_000)
    assert renglones["= Utilidad neta"] == pytest.approx(22_400_000)


def test_sin_utilidad_operativa_los_grados_no_se_calculan_y_se_explica():
    r = apalancamiento(100, 80, 50)
    assert r["uaii"] == -30
    assert r["gao"] is None and r["gaf"] is None and r["gat"] is None
    assert "punto de equilibrio" in r["lectura"]


def test_si_los_intereses_se_comen_la_uaii_el_gaf_queda_sin_dato():
    r = apalancamiento(100, 60, 30, intereses=15)
    assert r["gao"] == pytest.approx(40 / 10)
    assert r["gaf"] is None and r["gat"] is None
    assert "se la comen" in r["lectura"]


def test_los_impuestos_no_se_cobran_sobre_una_perdida():
    r = apalancamiento(100, 60, 30, intereses=15, tasa_impuestos=0.3)
    renglones = {f["renglon"]: f["valor"] for f in r["estado_resultados"]}
    assert renglones["− Impuestos"] == 0


def test_las_lecturas_van_a_la_colombiana():
    r = punto_equilibrio(125_000, 62_500, 6_000_000)
    assert "6.000.000" in r["lectura"]
    assert "6,000,000" not in r["lectura"]


# -------------------------------------------------------------------- API


@pytest.fixture
def cliente():
    from fastapi.testclient import TestClient
    from api import app
    return TestClient(app)


def test_el_api_calcula_el_equilibrio(cliente):
    r = cliente.post("/api/operativo/equilibrio", json={
        "precio": 125000, "costo_variable_unitario": 62500,
        "costos_fijos": 6000000, "unidades_programadas": 200})
    assert r.status_code == 200
    assert r.json()["punto_equilibrio_unidades"] == pytest.approx(96)


def test_el_api_devuelve_422_con_explicacion_si_no_hay_equilibrio(cliente):
    r = cliente.post("/api/operativo/equilibrio",
                     json={"precio": 100, "costo_variable_unitario": 120, "costos_fijos": 1000})
    assert r.status_code == 422
    assert "pierde plata" in r.json()["detail"]


def test_el_api_calcula_los_apalancamientos(cliente):
    r = cliente.post("/api/operativo/apalancamiento", json={
        "ventas": 300000000, "costos_variables": 200000000, "costos_fijos": 58000000,
        "intereses": 10000000, "tasa_impuestos": 0.30, "dividendos_preferentes": 8000000})
    assert r.status_code == 200
    d = r.json()
    assert d["gaf"] == pytest.approx(42 / 32)
    assert d["gaf_cartilla"] == pytest.approx(2.04, abs=0.01)
