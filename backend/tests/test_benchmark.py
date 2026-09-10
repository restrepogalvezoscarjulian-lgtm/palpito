"""Pruebas de la comparación contra el sector."""

from pathlib import Path

import pytest

from motor.benchmark import (
    HOLGURA,
    codigos_comparables,
    comparar,
    comparar_indicador,
)
from motor.modelos import EstadosFinancieros, Indicador
from motor.indicadores import calcular_todos

CASO = Path(__file__).resolve().parents[2] / "casos" / "comercial_andina.json"


@pytest.fixture(scope="module")
def ind():
    return calcular_todos(EstadosFinancieros.desde_json(CASO))


def _ind(codigo, nombre, valores, unidad="veces"):
    return Indicador(codigo=codigo, nombre=nombre, categoria="X",
                     valores=valores, unidad=unidad)


# ------------------------------------------------- no se inventan referencias


def test_sin_referencia_no_se_compara(ind):
    r = comparar(ind, {})
    assert r["disponible"] is False
    assert r["total_comparados"] == 0
    assert all(c["veredicto"] == "sin_referencia" for c in r["comparaciones"])


def test_sin_referencia_lo_dice_y_explica_por_que(ind):
    assert "no se pueden deducir" in comparar(ind, None)["lectura"]


def test_un_indicador_sin_dato_no_se_compara():
    c = comparar_indicador(_ind("razon_corriente", "Razón corriente", [None, None]), 1.8)
    assert c.veredicto == "sin_referencia"
    assert "no informa" in c.lectura


# ------------------------------------------------------- direccion de mejora


def test_estar_encima_es_favorable_cuando_subir_es_mejor():
    """Razón corriente: más alta que el sector es mejor."""
    c = comparar_indicador(_ind("razon_corriente", "Razón corriente", [2.5]), 1.8)
    assert c.posicion == "encima"
    assert c.veredicto == "favorable"


def test_estar_encima_es_desfavorable_cuando_bajar_es_mejor():
    """Endeudamiento: más alto que el sector es peor."""
    c = comparar_indicador(
        _ind("endeudamiento_activo", "Nivel de endeudamiento", [70.0], "%"), 45.0)
    assert c.posicion == "encima"
    assert c.veredicto == "desfavorable"


def test_estar_debajo_es_favorable_cuando_bajar_es_mejor():
    c = comparar_indicador(
        _ind("endeudamiento_activo", "Nivel de endeudamiento", [30.0], "%"), 45.0)
    assert c.posicion == "debajo"
    assert c.veredicto == "favorable"


def test_la_direccion_sale_del_mismo_sitio_que_el_puntaje():
    """Las dos lecturas no pueden contradecirse."""
    from motor.salud import CRITERIOS
    from motor.benchmark import MEJORA
    for c in CRITERIOS:
        assert MEJORA[c.codigo] == c.mejora


def test_sin_direccion_conocida_no_se_emite_juicio():
    c = comparar_indicador(_ind("inventado_xyz", "Indicador raro", [5.0]), 2.0)
    assert c.posicion == "encima"
    assert c.veredicto == "sin_criterio"
    assert "interprételo" in c.lectura


# -------------------------------------------------------------- la holgura


def test_una_diferencia_pequena_queda_en_linea():
    c = comparar_indicador(_ind("razon_corriente", "Razón corriente", [1.85]), 1.8)
    assert c.veredicto == "en_linea"
    assert "en línea" in c.lectura


def test_la_holgura_es_relativa_a_la_referencia():
    """Media décima no significa lo mismo sobre 1,8 que sobre 40."""
    chico = comparar_indicador(_ind("razon_corriente", "R", [2.3]), 1.8)
    grande = comparar_indicador(
        _ind("endeudamiento_activo", "E", [40.5], "%"), 40.0)
    assert chico.veredicto != "en_linea"
    assert grande.veredicto == "en_linea"


def test_justo_en_el_borde_de_la_holgura_sigue_en_linea():
    ref = 2.0
    c = comparar_indicador(
        _ind("razon_corriente", "R", [ref * (1 + HOLGURA)]), ref)
    assert c.veredicto == "en_linea"


# ------------------------------------------------------------- las cuentas


def test_la_brecha_se_reporta_absoluta_y_relativa():
    c = comparar_indicador(_ind("razon_corriente", "R", [2.7]), 1.8)
    assert c.brecha == pytest.approx(0.9)
    assert c.brecha_relativa == pytest.approx(50.0)


def test_se_usa_el_ultimo_periodo_informado():
    c = comparar_indicador(_ind("razon_corriente", "R", [1.0, 2.5]), 1.8)
    assert c.valor == 2.5


def test_se_ignora_un_ultimo_periodo_vacio():
    c = comparar_indicador(_ind("razon_corriente", "R", [2.5, None]), 1.8)
    assert c.valor == 2.5


def test_los_montos_no_se_comparan(ind):
    """Un monto depende del tamaño de la empresa: compararlo no dice nada."""
    codigos = {c["codigo"] for c in comparar(ind, {})["comparaciones"]}
    assert "capital_trabajo_neto" not in codigos
    assert "razon_corriente" in codigos


def test_el_resumen_cuenta_bien(ind):
    refs = {"razon_corriente": 1.0, "endeudamiento_activo": 90.0, "margen_neto": 7.4}
    r = comparar(ind, refs)
    assert r["disponible"] is True
    assert r["total_comparados"] == 3
    assert r["favorables"] + r["en_linea"] + r["desfavorables"] == 3
    assert r["sin_referencia"] > 0


def test_el_catalogo_sirve_para_armar_el_formulario(ind):
    cat = codigos_comparables(ind)
    assert cat
    assert all("codigo" in c and "nombre" in c for c in cat)
    assert all(c["codigo"] != "capital_trabajo_neto" for c in cat)


def test_se_dice_de_donde_sacar_las_referencias(ind):
    assert "Superintendencia de Sociedades" in comparar(ind, {})["nota_fuente"]


# ------------------------------------------------------------- el endpoint


@pytest.fixture(scope="module")
def cliente():
    from fastapi.testclient import TestClient
    from api import app
    return TestClient(app)


@pytest.fixture(scope="module")
def datos():
    import json
    with open(CASO, encoding="utf-8") as fh:
        return json.load(fh)


def test_el_endpoint_compara(cliente, datos):
    r = cliente.post("/api/benchmark", json={
        "estados": datos,
        "referencias": {"razon_corriente": 1.2, "margen_neto": 12.0},
    })
    assert r.status_code == 200
    c = r.json()
    assert c["disponible"] is True
    assert c["total_comparados"] == 2


def test_el_endpoint_sin_referencias_no_inventa(cliente, datos):
    r = cliente.post("/api/benchmark", json={"estados": datos, "referencias": {}})
    assert r.status_code == 200
    assert r.json()["disponible"] is False


def test_el_analisis_completo_incluye_benchmark(cliente):
    cuerpo = cliente.get("/api/casos/comercial_andina/analisis").json()
    assert "benchmark" in cuerpo
    assert "comparables" in cuerpo
    assert cuerpo["benchmark"]["disponible"] is False   # el caso no declara


def test_un_caso_que_declara_referencias_si_compara(cliente, datos):
    datos = dict(datos)
    datos["supuestos"] = {**datos["supuestos"], "benchmark": {"razon_corriente": 1.2}}
    r = cliente.post("/api/analizar", json=datos)
    assert r.status_code == 200
    assert r.json()["benchmark"]["disponible"] is True


def test_el_endpoint_rechaza_estados_mal_formados(cliente):
    r = cliente.post("/api/benchmark", json={
        "estados": {"periodos": ["2024"], "balance": {"efectivo": [1, 2]}},
        "referencias": {},
    })
    assert r.status_code == 422
