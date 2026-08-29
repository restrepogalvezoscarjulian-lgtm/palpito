"""Pruebas del motor de diagnostico financiero.

Cada prueba verifica una formula contra un valor calculado a mano.
Esta suite es la evidencia de auditoria del proyecto: responde al paso 4 del
taller ("verifiquen manualmente al menos 4 calculos clave") de forma
automatizada y repetible.

Correr con:  pytest -v
"""

from pathlib import Path

import pytest

from motor.modelos import EstadosFinancieros
from motor.indicadores import calcular_todos, dupont, puente_caja, analisis_horizontal
from motor.validacion import validar, semaforo, resumen

CASO = Path(__file__).resolve().parents[2] / "casos" / "comercial_andina.json"
TOL = 0.01  # tolerancia de comparacion


@pytest.fixture(scope="module")
def ef():
    return EstadosFinancieros.desde_json(CASO)


@pytest.fixture(scope="module")
def ind(ef):
    return calcular_todos(ef)


# =============================================== 1. CARGA E INTEGRIDAD BASICA


def test_carga_periodos(ef):
    assert ef.periodos == ["2023", "2024"]
    assert ef.empresa == "Comercial Andina S.A."


def test_cuenta_inexistente_no_revienta(ef):
    assert ef.cuenta("depreciacion") == [None, None]


def test_longitudes_inconsistentes_se_rechazan():
    with pytest.raises(ValueError, match="periodos"):
        EstadosFinancieros({"periodos": ["2023", "2024"], "balance": {"efectivo": [100]}})


def test_pasivo_total_se_arma_con_no_corrientes(ef):
    assert ef.pasivo_total(0) == pytest.approx(2900)
    assert ef.pasivo_total(1) == pytest.approx(3830)


def test_deuda_financiera_suma_cp_y_lp(ef):
    assert ef.deuda_financiera(0) == pytest.approx(1630)
    assert ef.deuda_financiera(1) == pytest.approx(2400)


# ================================================== 2. VALIDACION DE LOS DATOS


def test_detecta_descuadre_del_balance(ef):
    hallazgos = validar(ef)
    errores = [h for h in hallazgos if h.codigo == "ECUACION_CONTABLE"]
    assert len(errores) == 2, "Debe detectar el descuadre en ambos periodos"
    assert "550" in errores[0].mensaje
    assert "390" in errores[1].mensaje


def test_semaforo_rojo_por_descuadre(ef):
    assert semaforo(validar(ef)) == "rojo"


def test_detecta_partidas_no_informadas(ef):
    hallazgos = validar(ef)
    subtotales = [h for h in hallazgos if h.codigo == "SUBTOTAL_BALANCE"]
    assert len(subtotales) == 4  # 2 grupos x 2 periodos


def test_reporta_datos_faltantes(ef):
    faltantes = [h for h in validar(ef) if h.codigo == "DATO_FALTANTE"]
    codigos = " ".join(h.mensaje for h in faltantes)
    assert "depreciacion" in codigos


def test_balance_cuadrado_da_semaforo_limpio():
    datos = {
        "empresa": "Prueba S.A.", "periodos": ["2024"],
        "balance": {
            "efectivo": [100], "cuentas_por_cobrar": [200], "inventarios": [300],
            "activo_corriente": [600], "propiedad_planta_equipo": [400],
            "activo_total": [1000], "proveedores": [150], "deuda_financiera_cp": [50],
            "pasivo_corriente": [200], "deuda_financiera_lp": [300], "patrimonio": [500],
        },
        "resultados": {
            "ventas": [1000], "costo_ventas": [600], "utilidad_bruta": [400],
            "gastos_operacionales": [200], "utilidad_operacional": [200],
            "gastos_financieros": [50], "utilidad_antes_impuestos": [150],
            "impuestos": [45], "utilidad_neta": [105],
            "depreciacion": [30], "compras": [600], "ventas_credito": [1000],
        },
    }
    ef_ok = EstadosFinancieros(datos)
    assert semaforo(validar(ef_ok)) == "verde"


def test_detecta_cadena_de_resultados_rota():
    datos = {
        "periodos": ["2024"],
        "resultados": {
            "ventas": [1000], "costo_ventas": [600],
            "utilidad_bruta": [999],  # deberia ser 400
        },
    }
    hallazgos = validar(EstadosFinancieros(datos))
    assert any(h.codigo == "CADENA_RESULTADOS" for h in hallazgos)


def test_detecta_valores_negativos():
    datos = {"periodos": ["2024"], "balance": {"inventarios": [-50]}}
    hallazgos = validar(EstadosFinancieros(datos))
    assert any(h.codigo == "VALOR_NEGATIVO" for h in hallazgos)


# ========================= 3. LOS CUATRO CALCULOS QUE EXIGE EL TALLER (paso 4)


def test_razon_corriente(ind):
    """2950/1650 = 1.7879 ; 3620/2050 = 1.7659"""
    assert ind["razon_corriente"].valores[0] == pytest.approx(1.7879, abs=TOL)
    assert ind["razon_corriente"].valores[1] == pytest.approx(1.7659, abs=TOL)


def test_nivel_de_endeudamiento(ind):
    """Pasivo informado: 2900/5750 = 50.43% ; 3830/6870 = 55.75%"""
    assert ind["endeudamiento_activo"].valores[0] == pytest.approx(50.43, abs=TOL)
    assert ind["endeudamiento_activo"].valores[1] == pytest.approx(55.75, abs=TOL)


def test_margen_operativo(ind):
    """1530/8900 = 17.19% ; 1510/10600 = 14.25%"""
    assert ind["margen_operacional"].valores[0] == pytest.approx(17.19, abs=TOL)
    assert ind["margen_operacional"].valores[1] == pytest.approx(14.25, abs=TOL)


def test_margen_neto(ind):
    """917/8900 = 10.30% ; 784/10600 = 7.40%"""
    assert ind["margen_neto"].valores[0] == pytest.approx(10.30, abs=TOL)
    assert ind["margen_neto"].valores[1] == pytest.approx(7.40, abs=TOL)


# ============================== 4. EL ENDEUDAMIENTO CAMBIA SEGUN EL DESCUADRE


def test_endeudamiento_implicito_difiere_del_informado(ind):
    """La diferencia entre ambas medidas ES el descuadre del balance.

    Este es el hallazgo central del caso: reportar 50.4% en vez de 60.0%
    subestima el endeudamiento en casi 10 puntos.
    """
    informado = ind["endeudamiento_activo"].valores
    implicito = ind["endeudamiento_activo_implicito"].valores
    assert implicito[0] == pytest.approx(60.00, abs=TOL)
    assert implicito[1] == pytest.approx(61.43, abs=TOL)
    assert implicito[0] - informado[0] > 9  # brecha material


# =========================================== 5. LIQUIDEZ: LA TRAMPA DEL CASO


def test_razon_corriente_estable_pero_calidad_se_deteriora(ind):
    """La razon corriente casi no se mueve, pero el efectivo se derrumba."""
    rc = ind["razon_corriente"].valores
    assert abs(rc[1] - rc[0]) < 0.05, "La razon corriente parece estable"

    efectivo = ind["razon_efectivo"].valores
    assert efectivo[1] < efectivo[0] * 0.6, "El efectivo si cayo fuerte"


# ================================================= 6. ACTIVIDAD Y CICLO DE CAJA


def test_dias_cartera(ind):
    assert ind["dias_cartera"].valores[0] == pytest.approx(51.26, abs=0.1)
    assert ind["dias_cartera"].valores[1] == pytest.approx(57.85, abs=0.1)


def test_dias_inventario(ind):
    assert ind["dias_inventario"].valores[0] == pytest.approx(69.83, abs=0.1)
    assert ind["dias_inventario"].valores[1] == pytest.approx(75.59, abs=0.1)


def test_ciclo_de_efectivo_se_alarga(ind):
    ciclo = ind["ciclo_conversion_efectivo"].valores
    assert ciclo[0] == pytest.approx(62.69, abs=0.1)
    assert ciclo[1] == pytest.approx(79.59, abs=0.1)
    assert ciclo[1] - ciclo[0] == pytest.approx(16.9, abs=0.2)


def test_ktno(ind):
    """1250+1100-920 = 1430 ; 1680+1460-1040 = 2100"""
    assert ind["ktno"].valores[0] == pytest.approx(1430)
    assert ind["ktno"].valores[1] == pytest.approx(2100)


def test_pkt_empeora(ind):
    pkt = ind["pkt"].valores
    assert pkt[0] == pytest.approx(16.07, abs=TOL)
    assert pkt[1] == pytest.approx(19.81, abs=TOL)


# =================================================== 7. RENTABILIDAD Y DUPONT


def test_roa_usa_utilidad_operacional(ind):
    """1530/5750 = 26.61%. La cartilla del curso invierte esta division."""
    assert ind["roa"].valores[0] == pytest.approx(26.61, abs=TOL)


def test_roe(ind):
    assert ind["roe"].valores[0] == pytest.approx(39.87, abs=TOL)
    assert ind["roe"].valores[1] == pytest.approx(29.58, abs=TOL)


def test_dupont_reconstruye_el_roe(ef, ind):
    """El producto de los tres factores DEBE dar exactamente el ROE."""
    d = dupont(ef)
    for i in range(ef.n_periodos):
        assert d["factores"]["roe_reconstruido"][i] == pytest.approx(
            ind["roe"].valores[i], abs=TOL
        )


def test_dupont_atribuye_la_caida_al_margen(ef):
    """La caida del ROE es por margen, no por rotacion ni por apalancamiento."""
    var = dupont(ef)["variacion_por_factor_pct"]
    assert var["margen_neto"] < -25          # el margen se desploma
    assert abs(var["rotacion_activos"]) < 1  # la rotacion practicamente no se mueve
    assert var["multiplicador_patrimonio"] > 0  # el apalancamiento incluso sube


def test_cobertura_de_intereses_se_deteriora(ind):
    cob = ind["cobertura_intereses"].valores
    assert cob[0] == pytest.approx(6.95, abs=TOL)
    assert cob[1] == pytest.approx(3.87, abs=TOL)


def test_roic_cae_por_debajo_del_costo_de_la_deuda(ind):
    """Senal de destruccion de valor: el negocio rinde casi lo mismo que cuesta la plata."""
    roic = ind["roic"].valores[1]
    kd = ind["costo_deuda_implicito"].valores[1]
    assert roic == pytest.approx(19.76, abs=TOL)
    assert kd == pytest.approx(19.35, abs=TOL)
    assert roic - kd < 1.0  # margen practicamente nulo


def test_tasa_de_impuestos_es_consistente(ind):
    assert all(v == pytest.approx(30.0, abs=TOL) for v in ind["tasa_impuestos"].valores)


# ======================================================== 8. ANALISIS HORIZONTAL


def test_horizontal_costos_crecen_mas_que_ventas(ef):
    h = analisis_horizontal(ef)["resultados"]
    assert h["ventas"]["variacion_relativa"] == pytest.approx(19.10, abs=TOL)
    assert h["costo_ventas"]["variacion_relativa"] == pytest.approx(22.61, abs=TOL)
    assert h["gastos_financieros"]["variacion_relativa"] == pytest.approx(77.27, abs=TOL)
    assert h["utilidad_neta"]["variacion_relativa"] == pytest.approx(-14.50, abs=TOL)
    assert h["costo_ventas"]["variacion_relativa"] > h["ventas"]["variacion_relativa"]


def test_horizontal_cartera_e_inventario_crecen_mas_que_ventas(ef):
    b = analisis_horizontal(ef)["balance"]
    v = analisis_horizontal(ef)["resultados"]["ventas"]["variacion_relativa"]
    assert b["cuentas_por_cobrar"]["variacion_relativa"] == pytest.approx(34.40, abs=TOL)
    assert b["inventarios"]["variacion_relativa"] == pytest.approx(32.73, abs=TOL)
    assert b["cuentas_por_cobrar"]["variacion_relativa"] > v
    assert b["inventarios"]["variacion_relativa"] > v


# ============================================ 9. PUENTE DE CAJA (Oscar L. Garcia)


def test_puente_caja_explica_el_endeudamiento(ef):
    """La UODI no alcanzo para financiar KTNO + activos fijos.

    Por eso subio la deuda y bajo el efectivo. Es la respuesta a
    "vendi mas pero tengo menos plata".
    """
    p = puente_caja(ef)
    assert p["disponible"]
    assert p["uodi"] == pytest.approx(1057)
    assert p["aumento_ktno"] == pytest.approx(670)
    assert p["aumento_activos_fijos_neto"] == pytest.approx(450)
    assert p["flujo_caja_libre_aprox"] == pytest.approx(-63)
    assert p["flujo_caja_libre_aprox"] < 0, "Flujo de caja libre negativo"
    assert p["variacion_deuda_financiera"] == pytest.approx(770)
    assert p["variacion_efectivo"] == pytest.approx(-140)
    assert p["es_aproximacion"] is True


def test_puente_caja_exige_dos_periodos():
    ef1 = EstadosFinancieros({"periodos": ["2024"], "balance": {}, "resultados": {}})
    assert puente_caja(ef1)["disponible"] is False


# ============================================== 10. TRAZABILIDAD (modo docente)


def test_todo_indicador_declara_formula_e_insumos(ind):
    for codigo, i in ind.items():
        assert i.formula, f"{codigo} no declara su formula"
        assert i.insumos, f"{codigo} no declara sus insumos"
        assert i.nombre and i.categoria


def test_indicadores_sin_datos_reportan_no_disponible():
    """Si faltan cuentas, el indicador devuelve None, no un numero inventado."""
    ef_vacio = EstadosFinancieros({"periodos": ["2024"], "balance": {}, "resultados": {}})
    for i in calcular_todos(ef_vacio).values():
        assert not i.disponible, f"{i.codigo} invento un valor sin datos"


# ============================================= 11. MOTOR DE REGLAS (sin IA)

from motor.diagnostico import diagnosticar, recomendaciones


def test_diagnostico_detecta_las_alertas_centrales(ef):
    titulos = " | ".join(a.titulo for a in diagnosticar(ef))
    assert "costo de ventas crece mas rapido" in titulos
    assert "cartera crece mas rapido" in titulos
    assert "inventario crece mas rapido" in titulos
    assert "no genero caja suficiente" in titulos


def test_alertas_quedan_numeradas_sin_saltos(ef):
    al = diagnosticar(ef)
    assert [a.prioridad for a in al] == list(range(1, len(al) + 1))


def test_toda_alerta_trae_evidencia_numerica(ef):
    for a in diagnosticar(ef):
        assert a.evidencia, f"La alerta '{a.titulo}' no cita evidencia"
        assert a.cuentas, f"La alerta '{a.titulo}' no senala cuentas responsables"


def test_alerta_de_endeudamiento_advierte_el_descuadre(ef):
    al = [a for a in diagnosticar(ef) if "endeudamiento aument" in a.titulo]
    assert al, "Debe alertar el aumento del endeudamiento"
    assert any("61.43" in e for e in al[0].evidencia)


def test_recomendaciones_no_se_repiten(ef):
    recs = recomendaciones(diagnosticar(ef))
    assert len(recs) == 3
    assert len(set(recs)) == 3


def test_empresa_sana_no_dispara_alertas_criticas():
    """Control negativo: si el negocio va bien, el motor debe callarse."""
    datos = {
        "empresa": "Sana S.A.", "periodos": ["2023", "2024"],
        "balance": {
            "efectivo": [300, 500], "cuentas_por_cobrar": [400, 430],
            "inventarios": [300, 310], "activo_corriente": [1000, 1240],
            "propiedad_planta_equipo": [1000, 1010], "activo_total": [2000, 2250],
            "proveedores": [300, 360], "deuda_financiera_cp": [100, 90],
            "pasivo_corriente": [400, 450], "deuda_financiera_lp": [400, 350],
            "patrimonio": [1200, 1450],
        },
        "resultados": {
            "ventas": [3000, 3600], "costo_ventas": [1800, 2100],
            "utilidad_bruta": [1200, 1500], "gastos_operacionales": [600, 700],
            "utilidad_operacional": [600, 800], "gastos_financieros": [60, 55],
            "utilidad_antes_impuestos": [540, 745], "impuestos": [162, 223],
            "utilidad_neta": [378, 522],
        },
    }
    al = diagnosticar(EstadosFinancieros(datos))
    titulos = " | ".join(a.titulo for a in al)
    assert "no genero caja suficiente" not in titulos
    assert "cartera crece mas rapido" not in titulos
