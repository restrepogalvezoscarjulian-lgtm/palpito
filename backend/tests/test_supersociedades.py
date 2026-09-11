"""Pruebas de la construccion del benchmark sectorial.

Ninguna toca internet: la descarga esta separada del calculo justamente para
esto. Donde hace falta red, se inyecta un `traer` de mentira.

Las cifras de D1 S.A.S. que aparecen abajo son reales, descargadas del portal
el 11-sep-2026, y sirven de caso de referencia igual que el taller de Comercial
Andina sirve para el motor.
"""

import pytest

from herramientas.supersociedades import (
    CONCEPTOS_BALANCE,
    CONCEPTOS_RESULTADOS,
    MINIMO_EMPRESAS,
    armar_estados,
    construir_referencias,
    url_de_estados,
    urls_de_empresas,
)
from motor.modelos import EstadosFinancieros
from motor.indicadores import calcular_todos


# ------------------------------------------------------- el mapeo por nombre


def test_el_activo_por_el_otro_lado_no_entra_como_patrimonio():
    """"Total de patrimonio y pasivos" ES el activo total.

    Con el diccionario del importador de PDF -que busca subcadenas- ese
    concepto entraba como patrimonio por contener la palabra, y metia el activo
    entero en la casilla equivocada. Por eso aqui se mapea por nombre exacto.
    """
    assert "Total de patrimonio y pasivos" not in CONCEPTOS_BALANCE
    assert CONCEPTOS_BALANCE["Patrimonio total"] == "patrimonio"
    assert CONCEPTOS_BALANCE["Total de activos"] == "activo_total"


def test_el_pasivo_no_corriente_no_se_confunde_con_el_total():
    assert CONCEPTOS_BALANCE["Total de pasivos no corrientes"] == "pasivo_no_corriente"
    assert CONCEPTOS_BALANCE["Total pasivos"] == "pasivo_total"


def test_la_utilidad_neta_es_la_de_operaciones_continuadas():
    """La misma decision que gobierna el resto del motor."""
    assert CONCEPTOS_RESULTADOS[
        "Ganancia (pérdida) procedente de operaciones continuadas"] == "utilidad_neta"
    assert "Ganancia (pérdida)" not in CONCEPTOS_RESULTADOS


def test_la_deuda_financiera_se_deja_fuera_a_proposito():
    """En NIIF va mezclada con derivados bajo "Otros pasivos financieros".

    Sumarlos sobrestimaria el endeudamiento. Es la misma decision que se tomo
    con Almacenes Exito: mejor sin dato que con un dato adivinado.
    """
    for concepto in CONCEPTOS_BALANCE:
        assert "financiero" not in concepto.lower(), concepto
    assert "deuda_financiera_cp" not in CONCEPTOS_BALANCE.values()
    assert "deuda_financiera_lp" not in CONCEPTOS_BALANCE.values()


def test_un_concepto_desconocido_se_ignora_en_vez_de_adivinar():
    est = armar_estados(
        [{"concepto": "Bicicletas de la gerencia", "valor": "999", "periodo": "Periodo Actual"},
         {"concepto": "Total de activos", "valor": "500", "periodo": "Periodo Actual"},
         {"concepto": "Total de activos", "valor": "400", "periodo": "Periodo Anterior"}],
        [], empresa="Prueba", anio="2024")
    assert est["balance"]["activo_total"] == [400.0, 500.0]
    assert len(est["balance"]) == 1, est["balance"]


# ----------------------------------------------------------- el armado real


@pytest.fixture
def d1():
    """Cifras reales de D1 S.A.S., corte 2024. En miles de pesos."""
    balance = [
        ("Efectivo y equivalentes al efectivo", 978911280, 876429190),
        ("Cuentas comerciales por cobrar y otras cuentas por cobrar corrientes", 39374183, 47035551),
        ("Inventarios corrientes", 1356629231, 1170509278),
        ("Activos corrientes totales", 2578696126, 2337300728),
        ("Propiedades, planta y equipo", 3618986832, 3478100620),
        ("Total de activos", 6321816293, 5925201518),
        ("Cuentas por pagar comerciales y otras cuentas por pagar corrientes", 3420471188, 3100000000),
        ("Pasivos corrientes totales", 3774181652, 3393830955),
        ("Total de pasivos no corrientes", 2329934670, 2328739106),
        ("Total pasivos", 6104116322, 5722570061),
        ("Patrimonio total", 217699971, 202631457),
    ]
    resultados = [
        ("Ingresos de actividades ordinarias", 19440000000, 16800000000),
        ("Costo de ventas", 15552000000, 13440000000),
        ("Ganancia bruta", 3888000000, 3360000000),
        ("Ganancia (pérdida) por actividades de operación", 340000000, 280000000),
        ("Costos financieros", 210000000, 190000000),
        ("Ganancia (pérdida), antes de impuestos", 130000000, 90000000),
        ("Ingreso (gasto) por impuestos", 45000000, 30000000),
        ("Ganancia (pérdida) procedente de operaciones continuadas", 85000000, 60000000),
    ]
    def filas(pares):
        salida = []
        for concepto, actual, anterior in pares:
            salida.append({"concepto": concepto, "valor": str(actual), "periodo": "Periodo Actual"})
            salida.append({"concepto": concepto, "valor": str(anterior), "periodo": "Periodo Anterior"})
        return salida
    return filas(balance), filas(resultados)


def test_una_consulta_trae_dos_periodos(d1):
    """La taxonomia da "Periodo Actual" y "Periodo Anterior" del mismo corte."""
    est = armar_estados(*d1, empresa="D1 S.A.S.", anio="2024")
    assert est["periodos"] == ["2023", "2024"]
    assert est["balance"]["activo_total"] == [5925201518.0, 6321816293.0]


def test_los_estados_armados_pasan_por_el_motor_sin_tocarlo(d1):
    """El objetivo del modulo: que el motor de siempre los entienda."""
    est = armar_estados(*d1, empresa="D1 S.A.S.", anio="2024")
    ind = calcular_todos(EstadosFinancieros(est))
    # 2.578.696.126 / 3.774.181.652 = 0,683
    assert ind["razon_corriente"].valores[-1] == pytest.approx(0.683, abs=0.01)
    # Un discounter: rota rapidisimo y el proveedor le financia la operacion.
    assert ind["dias_inventario"].valores[-1] == pytest.approx(31.8, abs=1.0)
    assert ind["margen_bruto"].valores[-1] == pytest.approx(20.0, abs=0.5)


def test_la_unidad_no_afecta_los_ratios(d1):
    """Da igual que el archivo venga en pesos o en miles: al dividir se cancela."""
    bal, res = d1
    en_pesos = [dict(f, valor=str(float(f["valor"]) * 1000)) for f in bal]
    res_pesos = [dict(f, valor=str(float(f["valor"]) * 1000)) for f in res]
    a = calcular_todos(EstadosFinancieros(armar_estados(bal, res, anio="2024")))
    b = calcular_todos(EstadosFinancieros(armar_estados(en_pesos, res_pesos, anio="2024")))
    for c in ("razon_corriente", "margen_bruto", "endeudamiento_activo", "dias_inventario"):
        assert a[c].valores[-1] == pytest.approx(b[c].valores[-1], rel=1e-9), c


# ------------------------------------------------------ los cuartiles


def _empresa(razon_corriente_objetivo):
    """Una empresa sintetica con la razon corriente que se le pida."""
    return {
        "empresa": "X", "periodos": ["2023", "2024"],
        "balance": {"activo_corriente": [100, 100 * razon_corriente_objetivo],
                    "pasivo_corriente": [100, 100],
                    "activo_total": [200, 200], "patrimonio": [100, 100]},
        "resultados": {"ventas": [100, 100], "costo_ventas": [50, 50]},
    }


def test_se_publican_mediana_y_cuartiles_no_promedio():
    """Una empresa atipica no puede mover la referencia del sector."""
    normales = [_empresa(1.0 + i * 0.1) for i in range(12)]   # de 1,0 a 2,1
    atipica = _empresa(500.0)                                  # la que romperia un promedio
    sector = construir_referencias(normales + [atipica], ciiu="4711.00", anio=2024)
    rc = sector.referencias["razon_corriente"]
    assert 1.4 < rc.mediana < 1.8, rc.mediana
    assert rc.p25 < rc.mediana < rc.p75


def test_un_indicador_con_pocas_empresas_no_se_publica():
    """Con una muestra diminuta la mediana habla del azar, no del sector."""
    sector = construir_referencias([_empresa(1.5) for _ in range(MINIMO_EMPRESAS - 1)],
                                   ciiu="9999.00", anio=2024)
    assert "razon_corriente" not in sector.referencias


def test_una_empresa_con_datos_rotos_no_tumba_el_sector():
    buenas = [_empresa(1.0 + i * 0.1) for i in range(12)]
    rota = {"empresa": "Rota", "periodos": ["2024"], "balance": {"activo_corriente": [1, 2]}}
    sector = construir_referencias(buenas + [rota], ciiu="4711.00", anio=2024)
    assert "razon_corriente" in sector.referencias
    assert sector.empresas_usadas == 12


def test_el_archivo_guarda_de_donde_salio():
    """Una referencia sin procedencia no se puede sustentar, y no sirve."""
    sector = construir_referencias([_empresa(1.5) for _ in range(12)],
                                   ciiu="4711.00", anio=2024, nombre="Comercio al por menor")
    d = sector.como_dict()
    assert d["ciiu"] == "4711.00"
    assert d["anio"] == 2024
    assert "Superintendencia" in d["fuente"]
    assert d["descargado"]
    assert d["empresas_usadas"] == 12
    assert "razon_corriente" in d["benchmark"]
    assert d["cuartiles"]["razon_corriente"]["empresas"] == 12


def test_el_benchmark_sale_en_el_formato_que_espera_el_modulo_de_comparacion():
    """La app compara contra un dict {codigo: valor}."""
    from motor.benchmark import comparar

    sector = construir_referencias([_empresa(1.0 + i * 0.1) for i in range(12)],
                                   ciiu="4711.00", anio=2024)
    ef = EstadosFinancieros(_empresa(1.8))
    comparaciones = comparar(calcular_todos(ef), sector.como_dict()["benchmark"])
    assert comparaciones, "no comparo nada"


# --------------------------------------------------------------- las urls


def test_la_url_del_sector_filtra_por_ciiu_y_anio():
    u = urls_de_empresas("4711.00", 2024)
    assert "6cat-2gcs" in u and "4711.00" in u and "2024" in u


def test_la_url_de_estados_pide_un_solo_corte():
    u = url_de_estados("pfdp-zks5", "900276962", 2024)
    assert "nit=900276962" in u
    assert "2024-12-31" in u


def test_la_descarga_no_necesita_internet_para_probarse():
    """`traer` se inyecta: las pruebas no dependen de que el portal responda."""
    from herramientas.supersociedades import descargar_sector

    llamadas = []
    def traer_falso(url):
        llamadas.append(url)
        if "6cat-2gcs" in url:
            return [{"nit": "1", "raz_n_social": "Una S.A.S."}]
        return []          # sin balance: la empresa se descarta

    sector = descargar_sector("4711.00", 2024, traer_falso)
    assert sector.empresas_consultadas == 0, "una empresa sin balance no debe contar"
    assert any("6cat-2gcs" in u for u in llamadas)


# ------------------------------------------- las tildes rotas del portal
#
# El portal entrega el dato YA corrupto: en "Ganancia (perdida) por actividades
# de operacion" la vocal acentuada llega como U+FFFD, el rombo de "no pude leer
# esto". Los bytes son EF BF BD, o sea U+FFFD bien codificado en UTF-8: el dato
# se perdio antes de publicarse, no al descargarlo.
#
# Sin esto, los cuatro conceptos con tilde -utilidad operacional, utilidad
# neta, utilidad antes de impuestos y gastos de administracion- no empataban, y
# el benchmark salia sin margen operacional, sin margen neto, sin ROA y sin
# ROE. Con n=11 empresas, ningun error saltaba: los indicadores simplemente no
# aparecian.

ROTO = "\ufffd"


def test_el_concepto_empata_venga_roto_o_entero():
    from herramientas.supersociedades import RESULTADOS_POR_CLAVE, clave

    entero = "Ganancia (pérdida) por actividades de operación"
    del_portal = f"Ganancia (p{ROTO}rdida) por actividades de operaci{ROTO}n"
    assert clave(entero) == clave(del_portal)
    assert RESULTADOS_POR_CLAVE[clave(del_portal)] == "utilidad_operacional"


def test_los_cuatro_conceptos_con_tilde_se_reconocen_rotos():
    from herramientas.supersociedades import (RESULTADOS_POR_CLAVE,
                                              SUMADOS_POR_CLAVE, clave)
    esperado = {
        f"Ganancia (p{ROTO}rdida) por actividades de operaci{ROTO}n": "utilidad_operacional",
        f"Ganancia (p{ROTO}rdida) procedente de operaciones continuadas": "utilidad_neta",
        f"Ganancia (p{ROTO}rdida), antes de impuestos": "utilidad_antes_impuestos",
    }
    for concepto, cuenta in esperado.items():
        assert RESULTADOS_POR_CLAVE.get(clave(concepto)) == cuenta, concepto
    assert SUMADOS_POR_CLAVE.get(
        clave(f"Gastos de administraci{ROTO}n")) == "gastos_operacionales"


def test_la_ganancia_pelada_sigue_sin_entrar_aunque_venga_rota():
    """"Ganancia (perdida)" a secas incluye las discontinuadas."""
    from herramientas.supersociedades import RESULTADOS_POR_CLAVE, clave
    assert clave(f"Ganancia (p{ROTO}rdida)") not in RESULTADOS_POR_CLAVE


def test_ningun_par_de_conceptos_colapsa_al_mismo_esqueleto():
    """Lo que hace segura la comparacion por esqueleto ASCII.

    Si dos conceptos distintos produjeran la misma clave, uno pisaria al otro
    en silencio. Con 73 y 28 conceptos esto es verificable de una vez.
    """
    from herramientas.supersociedades import (CONCEPTOS_BALANCE,
                                              CONCEPTOS_RESULTADOS,
                                              CONCEPTOS_SUMADOS, clave)
    for grupo, nombre in ((CONCEPTOS_BALANCE, "balance"),
                          (CONCEPTOS_RESULTADOS, "resultados"),
                          (CONCEPTOS_SUMADOS, "sumados")):
        claves = [clave(k) for k in grupo]
        assert len(claves) == len(set(claves)), f"colision en {nombre}: {claves}"


def test_el_esqueleto_no_convierte_conceptos_distintos_en_el_mismo():
    from herramientas.supersociedades import clave
    assert clave("Total pasivos") != clave("Total de pasivos no corrientes")
    assert clave("Patrimonio total") != clave("Total de patrimonio y pasivos")
    assert clave("Inventarios corrientes") != clave("Inventarios no corrientes")


def test_d1_con_los_conceptos_rotos_produce_la_utilidad_neta():
    """De punta a punta, con el texto tal cual lo entrega el portal."""
    from herramientas.supersociedades import armar_estados

    filas = []
    for concepto, actual, anterior in [
        (f"Ganancia (p{ROTO}rdida) procedente de operaciones continuadas", 216598298, 180000000),
        (f"Ganancia (p{ROTO}rdida) por actividades de operaci{ROTO}n", 492883256, 400000000),
        ("Ingresos de actividades ordinarias", 9997387483, 8500000000),
    ]:
        filas.append({"concepto": concepto, "valor": str(actual), "periodo": "Periodo Actual"})
        filas.append({"concepto": concepto, "valor": str(anterior), "periodo": "Periodo Anterior"})

    est = armar_estados([], filas, empresa="D1", anio="2024")
    assert est["resultados"]["utilidad_neta"][-1] == 216598298.0
    assert est["resultados"]["utilidad_operacional"][-1] == 492883256.0
