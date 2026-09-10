"""Pruebas para estados financieros de empresas grandes.

Salieron de intentar importar el informe consolidado real de Ecopetrol 2024
(146 paginas, 3 MB). Lo que se aprendio ahi esta fijado aqui para que no se
vuelva a perder.
"""

import io

import pytest

from motor.importacion import (
    Tabla,
    _es_linea_de_indice,
    armar_estados,
    buscar_cuenta,
    importar,
    leer_pdf,
)
from motor.modelos import EstadosFinancieros
from motor.indicadores import calcular_todos
from motor.validacion import semaforo, validar


# ------------------------------------------------- la trampa del indice


def test_una_linea_de_tabla_de_contenido_no_es_una_cuenta():
    """En un indice el numero de la derecha es una pagina, no un saldo.

    El informe de Ecopetrol producia "Propiedades, planta y equipo = 63"
    leyendo su tabla de contenido.
    """
    assert _es_linea_de_indice(
        "14. Propiedades, planta y equipo............................ 63")
    assert _es_linea_de_indice(
        "Estados de situacion financiera consolidados ......................... 4")


def test_una_cuenta_de_verdad_no_se_confunde_con_el_indice():
    assert not _es_linea_de_indice("Efectivo y equivalentes de efectivo  12.450  10.980")
    assert not _es_linea_de_indice("Inventarios 9870000")
    assert not _es_linea_de_indice("Total activos 299.600")


def test_el_indice_se_descarta_al_leer_el_pdf():
    reportlab = pytest.importorskip("reportlab")
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.drawString(60, 720, "Contenido")
    c.drawString(60, 700, "Propiedades, planta y equipo............ 63")
    c.drawString(60, 680, "Inventarios............................. 44")
    c.drawString(60, 640, "Efectivo 12450 10980")
    c.save()

    tabla = Tabla()
    leer_pdf(buf.getvalue(), tabla)
    etiquetas = " ".join(f.etiqueta for f in tabla.filas)
    assert "Propiedades" not in etiquetas
    assert any("descartaron" in a for a in tabla.avisos)


# ------------------------------------------------ vocabulario de emisor


@pytest.mark.parametrize("etiqueta,cuenta", [
    ("Cuentas comerciales por pagar", "proveedores"),
    ("Cuentas comerciales y otras cuentas por pagar", "proveedores"),
    ("Cuentas comerciales por cobrar", "cuentas_por_cobrar"),
    ("Cuentas comerciales y otras cuentas por cobrar", "cuentas_por_cobrar"),
    ("Deudores comerciales y otras cuentas por cobrar", "cuentas_por_cobrar"),
])
def test_se_entiende_el_vocabulario_niif_de_los_emisores(etiqueta, cuenta):
    """Una empresa grande no dice "proveedores": dice "cuentas comerciales"."""
    assert buscar_cuenta(etiqueta)[0] == cuenta


# ------------------------------------------------------ escala de billones


CSV_GRANDE = """Cuenta;2023;2024
Efectivo y equivalentes de efectivo;12450000;10980000
Cuentas comerciales y otras cuentas por cobrar;18300000;17650000
Inventarios;9870000;10240000
Total activo corriente;48200000;46500000
Propiedad, planta y equipo;121400000;129800000
Total activos;280500000;299600000
Cuentas comerciales por pagar;22100000;23400000
Obligaciones financieras corto plazo;14800000;16200000
Total pasivo corriente;52300000;56100000
Obligaciones financieras largo plazo;78900000;84300000
Total patrimonio;118600000;124900000
Ingresos por ventas;143700000;133300000
Costo de ventas;89400000;86200000
Utilidad bruta;54300000;47100000
Gastos de administracion y ventas;18200000;17900000
Utilidad operacional;36100000;29200000
Gastos financieros;6800000;7900000
Utilidad antes de impuestos;29300000;21300000
Impuesto de renta;10300000;6400000
Utilidad neta;19000000;14900000
"""


@pytest.fixture(scope="module")
def tabla_grande():
    return importar("petrolera.csv", CSV_GRANDE.encode("utf-8"))


def test_se_reconocen_todas_las_cuentas_de_un_emisor(tabla_grande):
    reconocidas = [f for f in tabla_grande.filas if f.cuenta]
    assert len(reconocidas) == 20


@pytest.fixture(scope="module")
def estados_grandes(tabla_grande):
    return armar_estados(tabla_grande.como_dict(), empresa="Petrolera",
                         moneda="COP", unidad="millones")


def test_las_cifras_de_billones_no_se_deforman(estados_grandes):
    """Millones de millones tienen que llegar intactos hasta el calculo."""
    assert estados_grandes["balance"]["activo_total"] == [280500000, 299600000]
    assert estados_grandes["resultados"]["ventas"] == [143700000, 133300000]


def test_los_indicadores_salen_iguales_sin_importar_la_escala(estados_grandes):
    """Una razon es un cociente: la magnitud no la altera."""
    ef = EstadosFinancieros(estados_grandes)
    ind = calcular_todos(ef)
    # Activo corriente 46.500.000 / pasivo corriente 56.100.000
    assert ind["razon_corriente"].valores[-1] == pytest.approx(0.8289, abs=0.001)
    # Utilidad neta 14.900.000 / ventas 133.300.000
    assert ind["margen_neto"].valores[-1] == pytest.approx(11.178, abs=0.01)


def test_la_validacion_detecta_el_descuadre_a_cualquier_escala(estados_grandes):
    """El balance de esta prueba no cuadra por 34 billones, y se tiene que ver."""
    ef = EstadosFinancieros(estados_grandes)
    hallazgos = validar(ef)
    assert semaforo(hallazgos) == "rojo"
    assert any("no cuadra" in h.mensaje for h in hallazgos)


def test_ningun_indicador_revienta_con_cifras_grandes(estados_grandes):
    ind = calcular_todos(EstadosFinancieros(estados_grandes))
    for codigo, i in ind.items():
        for v in i.valores:
            assert v is None or isinstance(v, (int, float)), codigo


# ------------------------------------------- el signo de los estados publicados


def test_los_costos_negativos_se_voltean():
    """Los estados publicados traen costos y gastos entre parentesis.

    Nutresa reporta "Costos de ventas (12.457.813)" porque lo esta restando
    dentro del encadenamiento. El motor los espera como monto positivo, o los
    dias de inventario salen negativos.
    """
    cruda = {
        "periodos": ["2024", "2025"],
        "filas": [
            {"cuenta": "ventas", "valores": [18589956, 20578988]},
            {"cuenta": "costo_ventas", "valores": [-11304753, -12457813]},
            {"cuenta": "gastos_financieros", "valores": [-728099, -1547370]},
        ],
    }
    datos = armar_estados(cruda)
    assert datos["resultados"]["costo_ventas"] == [11304753.0, 12457813.0]
    assert datos["resultados"]["gastos_financieros"] == [728099.0, 1547370.0]


def test_el_volteo_de_signo_nunca_es_silencioso():
    cruda = {"periodos": ["2024"],
             "filas": [{"cuenta": "costo_ventas", "valores": [-500]}]}
    ajustes = armar_estados(cruda)["supuestos"]["ajustes_importacion"]
    assert any("costo_ventas" in a for a in ajustes)


def test_no_se_voltea_lo_que_si_puede_ser_negativo():
    """Una utilidad negativa es una perdida, y tiene que quedarse negativa."""
    cruda = {"periodos": ["2024"],
             "filas": [{"cuenta": "utilidad_neta", "valores": [-1500]},
                       {"cuenta": "patrimonio", "valores": [-200]}]}
    datos = armar_estados(cruda)
    assert datos["resultados"]["utilidad_neta"] == [-1500.0]
    assert datos["balance"]["patrimonio"] == [-200.0]
    assert "supuestos" not in datos or not datos["supuestos"].get("ajustes_importacion")


# ------------------------------------------------ acotar paginas de un PDF


@pytest.mark.parametrize("rango,esperado", [
    ("10-13", {10, 11, 12, 13}),
    ("10,12", {10, 12}),
    ("13-10", {10, 11, 12, 13}),     # al reves tambien vale
    ("5", {5}),
    ("", None),                       # sin rango: todas
    ("   ", None),
])
def test_el_rango_de_paginas_se_entiende(rango, esperado):
    from motor.importacion import _paginas_pedidas
    assert _paginas_pedidas(rango, 75) == esperado


def test_un_rango_fuera_del_documento_se_recorta():
    from motor.importacion import _paginas_pedidas
    assert _paginas_pedidas("70-999", 75) == {70, 71, 72, 73, 74, 75}


def test_un_rango_imposible_se_rechaza():
    from motor.importacion import _paginas_pedidas
    with pytest.raises(ValueError):
        _paginas_pedidas("900-999", 75)
    with pytest.raises(ValueError):
        _paginas_pedidas("abc", 75)


# ----------------------------------------- el signo de moneda en las cifras


@pytest.mark.parametrize("linea,esperado", [
    ("Total activo corriente $ 8.817.990 $ 6.416.225",
     ["Total activo corriente", "8.817.990", "6.416.225"]),
    ("Efectivo y equivalentes de efectivo 8 $ 3.195.196 $ 1.128.399",
     ["Efectivo y equivalentes de efectivo", "8", "3.195.196", "1.128.399"]),
    ("Inventarios, neto 11 2.558.764 2.447.873",
     ["Inventarios, neto", "11", "2.558.764", "2.447.873"]),
    ("Efectivo y equivalentes 450 380",
     ["Efectivo y equivalentes", "450", "380"]),
])
def test_el_signo_de_moneda_no_corta_la_fila(linea, esperado):
    """Asi vienen los estados publicados en Colombia."""
    from motor.importacion import _partir_linea
    assert _partir_linea(linea) == esperado
