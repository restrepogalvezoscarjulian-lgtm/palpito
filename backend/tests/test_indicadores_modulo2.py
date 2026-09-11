"""Los indicadores que el modulo 2 de la cartilla pide y que faltaban:
GAF, EBITDA, margen EBITDA y CAPEX. Anadidos el 11-sep-2026.

Todo se calcula desde los estados. Lo que no se puede calcular desde los
estados -GAO, GAT, punto de equilibrio: necesitan costos fijos y variables-
NO se inventa; queda para una calculadora aparte.
"""

import pytest

from motor.indicadores import calcular_todos
from motor.modelos import EstadosFinancieros


def _ef(**extra):
    datos = {
        "empresa": "Prueba", "periodos": ["2023", "2024"], "moneda": "COP", "unidad": "millones",
        "balance": {"propiedad_planta_equipo": [1000, 1150], "activo_total": [2000, 2300],
                    "patrimonio": [1200, 1300], "pasivo_total": [800, 1000]},
        "resultados": {"ventas": [3000, 3600], "utilidad_operacional": [300, 420],
                       "gastos_financieros": [50, 70], "utilidad_antes_impuestos": [250, 350],
                       "impuestos": [75, 105], "utilidad_neta": [175, 245]},
    }
    for k, v in extra.items():
        datos["resultados" if k in ("depreciacion",) else "balance"][k] = v
    return EstadosFinancieros(datos)


# ------------------------------------------------------------------- GAF


def test_gaf_es_uaii_sobre_uaii_menos_intereses():
    """Es el ejemplo de la cartilla (modulo 2, GAF): UAII 42, intereses 10.
    La cartilla mete dividendos y le da 1,3 con un denominador que no cuadra
    (FORMULAS.md §8.2); la formula estandar da 42/32 = 1,3125."""
    ef = EstadosFinancieros({
        "periodos": ["2024"], "balance": {},
        "resultados": {"utilidad_operacional": [42.0], "gastos_financieros": [10.0]},
    })
    assert calcular_todos(ef)["gaf"].valores[0] == pytest.approx(42 / 32)


def test_gaf_sin_deuda_es_uno():
    ef = EstadosFinancieros({"periodos": ["2024"], "balance": {},
                             "resultados": {"utilidad_operacional": [42.0], "gastos_financieros": [0.0]}})
    assert calcular_todos(ef)["gaf"].valores[0] == pytest.approx(1.0)


def test_gaf_no_se_calcula_si_los_intereses_se_comen_la_utilidad():
    """Dividir por cero o por negativo daria un numero sin sentido financiero."""
    ef = EstadosFinancieros({"periodos": ["2024"], "balance": {},
                             "resultados": {"utilidad_operacional": [42.0], "gastos_financieros": [50.0]}})
    assert calcular_todos(ef)["gaf"].valores[0] is None


# ---------------------------------------------------------------- EBITDA


def test_ebitda_suma_la_depreciacion_al_ebit():
    ind = calcular_todos(_ef(depreciacion=[60, 80]))
    assert ind["ebitda"].valores == [360, 500]
    assert ind["margen_ebitda"].valores[1] == pytest.approx(500 / 3600 * 100)


def test_ebitda_sin_depreciacion_dice_sin_dato_y_no_adivina():
    """Los estados por funcion de Supersociedades no traen depreciacion.
    Mejor sin dato que con un EBITDA igual al EBIT disfrazado."""
    ind = calcular_todos(_ef())
    assert ind["ebitda"].valores == [None, None]
    assert ind["margen_ebitda"].valores == [None, None]


# ----------------------------------------------------------------- CAPEX


def test_capex_es_el_cambio_en_ppe_mas_la_depreciacion():
    """PPE paso de 1000 a 1150 y se depreciaron 80: se compraron 230."""
    ind = calcular_todos(_ef(depreciacion=[60, 80]))
    assert ind["capex"].valores == [None, 230]
    assert ind["intensidad_capex"].valores[1] == pytest.approx(230 / 3600 * 100)


def test_capex_sin_depreciacion_reporta_solo_la_inversion_neta():
    """Se subestima a proposito y la nota lo dice: es lo que se puede
    sustentar con el balance."""
    ind = calcular_todos(_ef())
    assert ind["capex"].valores == [None, 150]
    assert "APROXIMACI" in ind["capex"].nota


def test_capex_no_tiene_dato_en_el_primer_periodo():
    assert calcular_todos(_ef(depreciacion=[60, 80]))["capex"].valores[0] is None


def test_los_indicadores_nuevos_viajan_con_formula_y_fuente():
    ind = calcular_todos(_ef(depreciacion=[60, 80]))
    for c in ("gaf", "ebitda", "margen_ebitda", "capex", "intensidad_capex"):
        assert ind[c].formula and ind[c].fuente and ind[c].insumos, c


def test_la_falta_de_depreciacion_avisa_que_afecta_al_capex():
    from motor.validacion import validar
    hallazgos = [h for h in validar(_ef()) if h.codigo == "DATO_FALTANTE" and "depreciacion" in h.mensaje]
    assert hallazgos and "CAPEX" in hallazgos[0].detalle
