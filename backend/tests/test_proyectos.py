"""Pruebas del modulo de evaluación de proyectos.

Los dos casos base salen de la sesion 6 del curso (2 de septiembre de 2026),
resueltos por el profesor en voz alta durante la clase. Se usan como patron
de verificacion: si el motor no reproduce esas cifras, el motor esta mal.

La excepción es la TIR del caso Espiga, donde el profesor dijo 16,7% y el
cálculo correcto da 15,6%. Ver test_tir_espiga_discrepa_de_la_clase.
"""

from __future__ import annotations

import pytest

from motor.proyectos import (
    Proyecto,
    calcular_wacc,
    escenarios,
    evaluar_proyecto,
    flujo_caja_mensual,
    flujos_descontados,
    indice_rentabilidad,
    payback_descontado,
    payback_simple,
    punto_de_quiebre,
    tasa_interna_retorno,
    tir_modificada,
    valor_presente,
    valor_presente_flujos,
    valor_presente_neto,
)


# ------------------------------------------------------------------ casos base


@pytest.fixture
def caso_clase() -> Proyecto:
    """Ejemplo que el profesor cálculo en Excel durante la sesion 6.

    Inversión 2.000, flujos 500/600/700/800/900, WACC 12%.
    Resultados dictados en clase: VP flujos 2.442, VPN 442, IR 1,22.
    """
    return Proyecto(
        nombre="Ejemplo de clase",
        inversion=2000,
        flujos=[500, 600, 700, 800, 900],
        tasa_descuento=0.12,
        unidad="millones",
    )


@pytest.fixture
def caso_espiga() -> Proyecto:
    """Panaderia Espiga S.A., el taller resuelto al final de la sesion 6.

    Inversión 1.500, flujos 400/500/600/700, tasa 10%, la junta exige
    recuperar en máximo 3 años.
    Resultados dictados en clase: VP flujos 1.706, VPN 206, payback
    descontado 3,57 años, IR 1,14.
    """
    return Proyecto(
        nombre="Panaderia Espiga S.A.",
        inversion=1500,
        flujos=[400, 500, 600, 700],
        tasa_descuento=0.10,
        plazo_exigido=3,
        unidad="millones",
    )


# ------------------------------------------------------------- valor presente


def test_valor_presente_es_la_formula_dictada():
    # VP = VF / (1 + i)^t
    assert valor_presente(500, 0.12, 1) == pytest.approx(446.43, abs=0.01)
    assert valor_presente(600, 0.12, 2) == pytest.approx(478.32, abs=0.01)


def test_valor_presente_en_periodo_cero_no_descuenta():
    assert valor_presente(2000, 0.12, 0) == 2000


def test_vp_flujos_reproduce_la_cifra_de_clase(caso_clase):
    # El profesor sumo 2.442 en el tablero.
    assert valor_presente_flujos(caso_clase) == pytest.approx(2442, abs=1)


def test_vp_flujos_espiga_reproduce_la_cifra_de_clase(caso_espiga):
    # El profesor sumo 1.706.
    assert valor_presente_flujos(caso_espiga) == pytest.approx(1706, abs=1)


# ----------------------------------------------------------------------- VPN


def test_vpn_reproduce_la_cifra_de_clase(caso_clase):
    assert valor_presente_neto(caso_clase) == pytest.approx(442, abs=1)


def test_vpn_espiga_reproduce_la_cifra_de_clase(caso_espiga):
    assert valor_presente_neto(caso_espiga) == pytest.approx(206, abs=1)


def test_vpn_es_vp_flujos_menos_inversion(caso_clase):
    esperado = valor_presente_flujos(caso_clase) - caso_clase.inversion
    assert valor_presente_neto(caso_clase) == pytest.approx(esperado)


def test_vpn_negativo_cuando_la_tasa_exigida_es_alta(caso_espiga):
    caso_espiga.tasa_descuento = 0.40
    assert valor_presente_neto(caso_espiga) < 0


def test_inversion_entra_negativa_aunque_se_pase_positiva():
    p = Proyecto(inversion=1000, flujos=[600, 600], tasa_descuento=0.10)
    assert p.serie_completa()[0] == -1000


def test_inversion_ya_negativa_no_se_invierte_dos_veces():
    p = Proyecto(inversion=-1000, flujos=[600, 600], tasa_descuento=0.10)
    assert p.serie_completa()[0] == -1000


# ----------------------------------------------------------------------- TIR


def test_tir_hace_el_vpn_igual_a_cero(caso_clase):
    tir = tasa_interna_retorno(caso_clase)
    caso_clase.tasa_descuento = tir
    assert valor_presente_neto(caso_clase) == pytest.approx(0, abs=0.01)


def test_tir_espiga_discrepa_de_la_clase(caso_espiga):
    """El profesor dijo 16,7%; el cálculo correcto da 15,6%.

    Se verifica que 16,7% es imposible: a esa tasa los flujos descontados no
    alcanzan a cubrir la inversión, o sea el VPN sería negativo, y el propio
    profesor concluyo que era positivo. Documentado en FÓRMULAS.md sección 8.
    """
    tir = tasa_interna_retorno(caso_espiga)
    assert tir == pytest.approx(0.1563, abs=0.001)

    caso_espiga.tasa_descuento = 0.167
    assert valor_presente_neto(caso_espiga) < 0


def test_tir_mayor_que_wacc_cuando_el_vpn_es_positivo(caso_espiga):
    assert tasa_interna_retorno(caso_espiga) > caso_espiga.tasa_descuento
    assert valor_presente_neto(caso_espiga) > 0


def test_tir_sin_cambio_de_signo_no_existe():
    p = Proyecto(inversion=0, flujos=[100, 200], tasa_descuento=0.10)
    assert tasa_interna_retorno(p) is None


def test_tir_modificada_queda_entre_el_wacc_y_la_tir(caso_espiga):
    """La TIRM corrige el supuesto optimista de reinversión de la TIR."""
    wacc = caso_espiga.tasa_descuento
    tir = tasa_interna_retorno(caso_espiga)
    tirm = tir_modificada(caso_espiga)
    assert wacc < tirm < tir


def test_tir_modificada_reinvierte_a_la_tasa_que_se_le_pase(caso_espiga):
    baja = tir_modificada(caso_espiga, tasa_reinversion=0.02)
    alta = tir_modificada(caso_espiga, tasa_reinversion=0.30)
    assert alta > baja


# ------------------------------------------------------------------- payback


def test_payback_simple_espiga_da_tres_anios_justos(caso_espiga):
    # 400 + 500 + 600 = 1.500, la inversion exacta.
    assert payback_simple(caso_espiga) == pytest.approx(3.0, abs=0.01)


def test_payback_descontado_espiga_reproduce_la_cifra_de_clase(caso_espiga):
    # El profesor calculo 3,57 anios.
    assert payback_descontado(caso_espiga) == pytest.approx(3.57, abs=0.01)


def test_el_payback_descontado_cambia_la_recomendacion(caso_espiga):
    """El punto entero del ejercicio: simple cumple el plazo, descontado no."""
    assert payback_simple(caso_espiga) <= caso_espiga.plazo_exigido
    assert payback_descontado(caso_espiga) > caso_espiga.plazo_exigido


def test_payback_es_none_si_no_se_recupera():
    p = Proyecto(inversion=10000, flujos=[10, 10], tasa_descuento=0.10)
    assert payback_simple(p) is None
    assert payback_descontado(p) is None


# ----------------------------------------------------- indice de rentabilidad


def test_indice_rentabilidad_reproduce_la_cifra_de_clase(caso_clase):
    assert indice_rentabilidad(caso_clase) == pytest.approx(1.22, abs=0.01)


def test_indice_rentabilidad_espiga_reproduce_la_cifra_de_clase(caso_espiga):
    assert indice_rentabilidad(caso_espiga) == pytest.approx(1.14, abs=0.01)


def test_indice_rentabilidad_mayor_a_uno_equivale_a_vpn_positivo(caso_espiga):
    assert (indice_rentabilidad(caso_espiga) > 1) == (valor_presente_neto(caso_espiga) > 0)


def test_indice_rentabilidad_sin_inversion_no_existe():
    p = Proyecto(inversion=0, flujos=[100], tasa_descuento=0.10)
    assert indice_rentabilidad(p) is None


# ---------------------------------------------------------------------- WACC


def test_wacc_pondera_patrimonio_y_deuda():
    # 60% patrimonio al 18%, 40% deuda al 12% con impuestos del 35%.
    # 0,6 x 0,18 + 0,4 x 0,12 x 0,65 = 0,108 + 0,0312 = 0,1392
    r = calcular_wacc(
        patrimonio=600, deuda=400,
        costo_patrimonio=0.18, costo_deuda=0.12, tasa_impuestos=0.35,
    )
    assert r["valor"] == pytest.approx(0.1392, abs=0.0001)
    assert r["peso_patrimonio"] == pytest.approx(0.6)
    assert r["peso_deuda"] == pytest.approx(0.4)


def test_wacc_sin_deuda_es_el_costo_del_patrimonio():
    r = calcular_wacc(1000, 0, 0.18, 0.12, 0.35)
    assert r["valor"] == pytest.approx(0.18)


def test_el_escudo_fiscal_abarata_la_deuda():
    con = calcular_wacc(500, 500, 0.18, 0.12, 0.35)
    sin = calcular_wacc(500, 500, 0.18, 0.12, 0.0)
    assert con["valor"] < sin["valor"]
    assert con["escudo_fiscal"] > 0


def test_wacc_reporta_lo_que_falta_en_vez_de_reventar():
    r = calcular_wacc(None, 400, 0.18, 0.12, 0.35)
    assert r["valor"] is None
    assert "patrimonio" in r["faltantes"]


def test_wacc_sin_capital_no_se_calcula():
    assert calcular_wacc(0, 0, 0.18, 0.12, 0.35)["valor"] is None


# -------------------------------------------------------------- flujo mensual


def _doce_meses(entradas: float, salidas: float) -> list[dict]:
    nombres = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
    ]
    return [
        {"mes": n, "entradas": {"recaudos": entradas}, "salidas": {"gastos": salidas}}
        for n in nombres
    ]


def test_flujo_mensual_encadena_el_saldo():
    """El saldo final de un mes es el inicial del siguiente."""
    r = flujo_caja_mensual(150, _doce_meses(420, 407))
    assert r["meses"][0]["saldo_inicial"] == 150
    assert r["meses"][0]["flujo_neto"] == pytest.approx(13)
    assert r["meses"][0]["saldo_final"] == pytest.approx(163)
    assert r["meses"][1]["saldo_inicial"] == pytest.approx(163)


def test_flujo_mensual_detecta_el_mes_en_que_se_agota_la_caja():
    """El caso del profesor: el CAPEX de marzo descalza la operación."""
    meses = _doce_meses(420, 407)
    meses[2]["salidas"]["capex"] = 600  # marzo
    r = flujo_caja_mensual(150, meses)
    assert r["hay_deficit"] is True
    assert r["meses_en_deficit"][0] == "Marzo"
    assert r["faltante_maximo"] > 0


def test_flujo_mensual_sin_deficit_lo_reporta():
    r = flujo_caja_mensual(150, _doce_meses(420, 407))
    assert r["hay_deficit"] is False
    assert r["meses_en_deficit"] == []
    assert r["faltante_maximo"] == 0


def test_un_proyecto_rentable_puede_quedarse_sin_caja(caso_espiga):
    """VPN positivo y aún así la empresa quiebra: el punto de la clase."""
    assert valor_presente_neto(caso_espiga) > 0
    meses = _doce_meses(50, 40)
    meses[6]["salidas"]["materia_prima"] = 600  # julio, temporada navidena
    r = flujo_caja_mensual(80, meses)
    assert r["hay_deficit"] is True


def test_el_faltante_maximo_es_el_monto_a_financiar():
    meses = _doce_meses(100, 100)
    meses[3]["salidas"]["capex"] = 250
    r = flujo_caja_mensual(50, meses)
    assert r["faltante_maximo"] == pytest.approx(200)


# --------------------------------------------------- escenarios y sensibilidad


def test_escenarios_ordenan_el_vpn_de_menor_a_mayor(caso_espiga):
    res = escenarios(caso_espiga)
    assert [e["codigo"] for e in res] == ["conservador", "base", "optimista"]
    assert res[0]["vpn"] < res[1]["vpn"] < res[2]["vpn"]


def test_el_escenario_base_es_el_proyecto_sin_tocar(caso_espiga):
    base = escenarios(caso_espiga)[1]
    assert base["vpn"] == pytest.approx(valor_presente_neto(caso_espiga))


def test_la_inversion_no_se_mueve_entre_escenarios(caso_espiga):
    from motor.proyectos import aplicar_escenario
    assert aplicar_escenario(caso_espiga, -0.20).inversion == caso_espiga.inversion


def test_punto_de_quiebre_mide_la_holgura(caso_espiga):
    """Espiga aguanta ~12% de caida: VPN 206 sobre VP de 1.706."""
    q = punto_de_quiebre(caso_espiga)
    assert q["caida_tolerada"] == pytest.approx(0.1207, abs=0.001)


def test_en_el_punto_de_quiebre_el_vpn_es_cero(caso_espiga):
    from motor.proyectos import aplicar_escenario
    q = punto_de_quiebre(caso_espiga)
    al_limite = aplicar_escenario(caso_espiga, q["holgura"])
    assert valor_presente_neto(al_limite) == pytest.approx(0, abs=0.01)


def test_punto_de_quiebre_avisa_cuando_ya_se_destruye_valor(caso_espiga):
    caso_espiga.tasa_descuento = 0.40
    q = punto_de_quiebre(caso_espiga)
    assert q["holgura"] > 0
    assert "subir" in q["lectura"]


# ------------------------------------------------------------------ veredicto


def test_evaluacion_completa_de_espiga_sale_con_reparos(caso_espiga):
    """Crea valor pero incumple el plazo de la junta: amarillo, no verde."""
    r = evaluar_proyecto(caso_espiga)
    assert r["veredicto"] == "viable con reparos"
    assert r["semaforo"] == "amarillo"
    assert any("Payback descontado" in x for x in r["reparos"])


def test_un_proyecto_sin_reparos_sale_verde(caso_clase):
    r = evaluar_proyecto(caso_clase)
    assert r["semaforo"] == "verde"
    assert r["veredicto"] == "viable"
    assert r["reparos"] == []


def test_un_proyecto_que_destruye_valor_sale_rojo(caso_espiga):
    caso_espiga.tasa_descuento = 0.45
    r = evaluar_proyecto(caso_espiga)
    assert r["semaforo"] == "rojo"
    assert r["veredicto"] == "no viable"
    assert "No se recomienda" in r["recomendacion"]


def test_cada_metrica_viaja_con_su_trazabilidad(caso_espiga):
    """Modo docente: fórmula, fuente, criterio y tooltip en cada metrica."""
    for m in evaluar_proyecto(caso_espiga)["metricas"]:
        assert m["formula"], f"{m['codigo']} sin formula"
        assert m["fuente"], f"{m['codigo']} sin fuente"
        assert m["criterio"], f"{m['codigo']} sin criterio"
        assert m["ayuda"], f"{m['codigo']} sin tooltip"
        assert m["veredicto"] in {"favorable", "limite", "desfavorable", "sin_dato"}


def test_la_evaluacion_incluye_las_siete_metricas(caso_espiga):
    codigos = {m["codigo"] for m in evaluar_proyecto(caso_espiga)["metricas"]}
    assert codigos == {
        "vpn", "vp_flujos", "tir", "tir_modificada",
        "payback_simple", "payback_descontado", "indice_rentabilidad",
    }


def test_la_tabla_de_descuento_se_puede_auditar_renglon_a_renglon(caso_espiga):
    """Cada fila debe cuadrar con un Excel hecho a mano."""
    filas = flujos_descontados(caso_espiga)
    assert len(filas) == 5  # t=0 mas cuatro anios
    assert filas[0]["valor_presente"] == pytest.approx(-1500)
    assert filas[1]["valor_presente"] == pytest.approx(363.64, abs=0.01)
    assert filas[-1]["acumulado"] == pytest.approx(valor_presente_neto(caso_espiga))


# ------------------------------------------------ el separador decimal
#
# En la tarjeta del punto de quiebre convivian "12,1%" -del frontend- y
# "12.1%" -del motor-, uno debajo del otro. El formato de Python trae punto;
# en Colombia la coma separa los decimales.


def test_los_porcentajes_del_motor_llevan_coma_decimal():
    from motor.proyectos import _pct
    assert _pct(12.1) == "12,1"
    assert _pct(15.62, 2) == "15,62"
    assert "." not in _pct(1234.5)


def test_ningun_texto_del_proyecto_mezcla_punto_y_coma():
    """Barre la evaluacion entera buscando un decimal con punto."""
    import re
    from motor.proyectos import Proyecto, evaluar_proyecto

    ev = evaluar_proyecto(Proyecto(nombre="Prueba", inversion=1500,
                          flujos=[400, 500, 600, 700], tasa_descuento=0.10,
                          plazo_exigido=3))

    textos = []
    def recoge(o):
        if isinstance(o, dict):
            for v in o.values(): recoge(v)
        elif isinstance(o, list):
            for v in o: recoge(v)
        elif isinstance(o, str):
            textos.append(o)
    recoge(ev if isinstance(ev, dict) else ev.__dict__)

    # Un punto seguido de EXACTAMENTE tres cifras es el separador de miles y
    # esta bien ("1.705,8"). Uno seguido de una o dos es un decimal a la
    # inglesa ("3.57"), que es lo que se busca.
    malos = [t for t in textos if re.search(r"\d\.\d{1,2}(?!\d)", t)]
    assert not malos, f"decimales con punto: {malos[:5]}"
    # Y la coma de miles inglesa tampoco: "1,705.8"
    ingleses = [t for t in textos if re.search(r"\d,\d{3}\.", t)]
    assert not ingleses, f"formato ingles: {ingleses[:5]}"
