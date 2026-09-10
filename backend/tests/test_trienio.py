"""Pruebas del caso de tres periodos.

El motor nunca supuso dos periodos: compara siempre el primero contra el
ultimo. Estas pruebas fijan ese comportamiento, para que nadie lo rompa
cableando un indice.
"""

from pathlib import Path

import pytest

from motor.modelos import EstadosFinancieros
from motor.indicadores import analisis_horizontal, calcular_todos
from motor.diagnostico import diagnosticar
from motor.salud import puntaje_salud

CASO = Path(__file__).resolve().parents[2] / "casos" / "andina_trienio.json"


@pytest.fixture(scope="module")
def ef():
    return EstadosFinancieros.desde_json(CASO)


@pytest.fixture(scope="module")
def ind(ef):
    return calcular_todos(ef)


def test_el_caso_trae_tres_periodos(ef):
    assert ef.periodos == ["2022", "2023", "2024"]
    assert ef.n_periodos == 3


def test_cada_indicador_trae_un_valor_por_periodo(ind):
    for codigo, i in ind.items():
        assert len(i.valores) == 3, f"{codigo} no trae tres valores"


@pytest.mark.parametrize("codigo", [
    "razon_corriente", "margen_bruto", "margen_neto", "roe",
    "cobertura_intereses",
])
def test_los_indicadores_que_deben_caer_caen_monotonamente(ind, codigo):
    """La historia del caso es un deterioro sostenido, no un tropiezo aislado."""
    v = ind[codigo].valores
    assert v[0] > v[1] > v[2], f"{codigo} no cae de forma sostenida: {v}"


@pytest.mark.parametrize("codigo", ["dias_cartera", "dias_inventario"])
def test_los_indicadores_que_deben_subir_suben(ind, codigo):
    v = ind[codigo].valores
    assert v[0] < v[1] < v[2], f"{codigo} no sube de forma sostenida: {v}"


def test_la_variacion_compara_el_primero_contra_el_ultimo(ind):
    i = ind["margen_neto"]
    assert i.variacion() == pytest.approx(i.valores[-1] - i.valores[0])


def test_el_horizontal_va_de_2022_a_2024(ef):
    h = analisis_horizontal(ef)["resultados"]["ventas"]
    assert h["inicial"] == 7500
    assert h["final"] == 10600


def test_el_puntaje_castiga_mas_la_tendencia_larga(ef):
    """Con tres puntos la caida es mas evidente que con dos."""
    dos = puntaje_salud(EstadosFinancieros.desde_json(
        CASO.parent / "comercial_andina.json"))
    tres = puntaje_salud(ef)
    assert tres["puntaje"] < dos["puntaje"]


def test_el_balance_sigue_descuadrado_en_los_tres_periodos(ef):
    """Es la funcionalidad del caso, no un descuido que haya que arreglar."""
    for i in range(ef.n_periodos):
        activo = ef.valor("activo_total", i)
        pasivo = ef.pasivo_total(i)
        patrimonio = ef.valor("patrimonio", i)
        assert activo != pasivo + patrimonio


def test_el_puntaje_del_trienio_sigue_marcado_no_confiable(ef):
    assert puntaje_salud(ef)["confiable"] is False


def test_el_diagnostico_levanta_alertas_en_el_trienio(ef):
    assert len(diagnosticar(ef)) > 0
