"""Pruebas de la importacion de archivos.

Aqui se juega la confianza en todo lo demas: si una cifra entra mal, los 26
indicadores salen mal y el diagnostico es basura bien presentada. Por eso se
prueba con los formatos reales de una contabilidad colombiana, incluidos los
casos feos: parentesis por negativos, puntos de miles, celdas vacias y filas
que reclaman la misma cuenta.

Correr con:  pytest -v
"""

import io

import pytest

from motor.importacion import (
    armar_estados,
    buscar_cuenta,
    importar,
    leer_numero,
    normalizar,
    parece_periodo,
)
from motor.modelos import EstadosFinancieros


# ==================================================== 1. LECTURA DE NUMEROS


@pytest.mark.parametrize("bruto, esperado", [
    ("1.234.567,89", 1234567.89),   # colombiano: punto de miles, coma decimal
    ("1,234,567.89", 1234567.89),   # ingles
    ("$ 2.450", 2450.0),            # con simbolo de moneda
    ("2.450", 2450.0),              # un punto con tres digitos detras es miles
    ("2,5", 2.5),                   # una coma con un digito detras es decimal
    ("(550)", -550.0),              # parentesis contable = negativo
    ("-550", -550.0),
    ("0", 0.0),
    (1500, 1500.0),
    (1500.5, 1500.5),
])
def test_leer_numero_formatos_reales(bruto, esperado):
    assert leer_numero(bruto) == pytest.approx(esperado)


@pytest.mark.parametrize("bruto", ["", "   ", "-", "n/d", "N/A", None, "texto",
                                   "Cuentas por cobrar", True])
def test_lo_que_no_es_cifra_devuelve_none_no_cero(bruto):
    """Un dato ausente no puede volverse cero: el motor los distingue."""
    assert leer_numero(bruto) is None


def test_un_valor_ausente_no_se_rellena_con_cero():
    """Si una cuenta no trae dato en un periodo, entra como None."""
    cruda = {
        "periodos": ["2023", "2024"],
        "filas": [{"cuenta": "efectivo", "valores": ["100", "-"]}],
    }
    datos = armar_estados(cruda)
    assert datos["balance"]["efectivo"] == [100.0, None]


# =================================================== 2. NOMBRES DE LAS CUENTAS


def test_normalizar_quita_tildes_y_puntuacion():
    assert normalizar("  Depreciación y amortización  ") == "depreciacion y amortizacion"
    assert normalizar("PROPIEDAD, PLANTA Y EQUIPO") == "propiedad planta y equipo"


@pytest.mark.parametrize("etiqueta, cuenta", [
    ("Cuentas por cobrar", "cuentas_por_cobrar"),
    ("Deudores comerciales", "cuentas_por_cobrar"),
    ("CARTERA CLIENTES", "cuentas_por_cobrar"),
    ("Efectivo y equivalentes", "efectivo"),
    ("Caja y bancos", "efectivo"),
    ("Propiedad, planta y equipo", "propiedad_planta_equipo"),
    ("Activos fijos", "propiedad_planta_equipo"),
    ("Total activo", "activo_total"),
    ("Obligaciones financieras corto plazo", "deuda_financiera_cp"),
    ("Ingresos operacionales", "ventas"),
    ("Costo de ventas", "costo_ventas"),
    ("Utilidad antes de impuestos", "utilidad_antes_impuestos"),
    ("Resultado del ejercicio", "utilidad_neta"),
    ("Gastos de administración y ventas", "gastos_operacionales"),
])
def test_el_diccionario_reconoce_sinonimos_comunes(etiqueta, cuenta):
    assert buscar_cuenta(etiqueta)[0] == cuenta


def test_la_frase_mas_larga_gana():
    """"Utilidad antes de impuestos" no puede confundirse con "utilidad neta"."""
    assert buscar_cuenta("Utilidad antes de impuestos")[0] == "utilidad_antes_impuestos"
    assert buscar_cuenta("Utilidad operacional")[0] == "utilidad_operacional"
    assert buscar_cuenta("Utilidad bruta")[0] == "utilidad_bruta"


def test_encabezados_y_ruido_no_son_cuentas():
    for basura in ("Cuenta", "Concepto", "Nota", "Estado de resultados", ""):
        assert buscar_cuenta(basura)[0] is None


def test_periodos_en_los_encabezados():
    assert parece_periodo("2024") == "2024"
    assert parece_periodo("Dic-2024") == "Dic-2024"
    assert parece_periodo("Cuentas") is None
    assert parece_periodo("") is None


# ======================================================== 3. ARCHIVOS REALES


def _excel(matriz):
    from openpyxl import Workbook

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Balance"
    for fila in matriz:
        hoja.append(fila)
    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


MATRIZ = [
    ["Cuenta", "2023", "2024"],
    ["Efectivo y equivalentes", 450, 380],
    ["Deudores comerciales", 1800, 2400],
    ["Inventarios", 2100, 2900],
    ["Total activo corriente", 4350, 5680],
    ["Propiedad, planta y equipo", 3200, 3900],
    ["Total activo", 7550, 9580],
    ["Proveedores", 1200, 1500],
    ["Total pasivo corriente", 2100, 2800],
    ["Patrimonio", 3900, 4200],
    ["Ingresos operacionales", 9800, 11200],
    ["Costo de ventas", 6300, 7500],
    ["Utilidad bruta", 3500, 3700],
    ["Utilidad operacional", 1400, 1300],
    ["Utilidad neta", 820, 700],
]


def test_importar_excel_completo():
    tabla = importar("balance.xlsx", _excel(MATRIZ))
    assert tabla.periodos == ["2023", "2024"]
    assert len(tabla.filas) == len(MATRIZ) - 1
    asignadas = {f.cuenta for f in tabla.filas if f.cuenta}
    assert {"efectivo", "cuentas_por_cobrar", "inventarios", "activo_total",
            "ventas", "utilidad_neta"} <= asignadas


def test_importar_excel_conserva_las_cifras():
    tabla = importar("balance.xlsx", _excel(MATRIZ))
    fila = next(f for f in tabla.filas if f.cuenta == "cuentas_por_cobrar")
    assert fila.valores == [1800.0, 2400.0]


def test_importar_csv_con_punto_y_coma_y_formato_colombiano():
    contenido = (
        "Cuenta;2023;2024\n"
        "Efectivo;450;380\n"
        "Deudores comerciales;1.800;2.400\n"
        "Inventarios;2.100;2.900\n"
        "Ingresos operacionales;9.800;11.200\n"
        "Utilidad neta;(120);700\n"
    ).encode("utf-8")
    tabla = importar("estados.csv", contenido)
    assert tabla.periodos == ["2023", "2024"]
    cxc = next(f for f in tabla.filas if f.cuenta == "cuentas_por_cobrar")
    assert cxc.valores == [1800.0, 2400.0]
    neta = next(f for f in tabla.filas if f.cuenta == "utilidad_neta")
    assert neta.valores == [-120.0, 700.0]


def test_dos_filas_que_reclaman_la_misma_cuenta_no_se_pisan():
    """Si dos filas se parecen a la misma cuenta, una queda libre y avisa.

    Adivinar en silencio cual de las dos era la buena es la forma mas facil de
    arruinar un balance sin que nadie se entere.
    """
    contenido = (
        "Cuenta;2024\n"
        "Inventarios;2.100\n"
        "Inventarios en transito;300\n"
    ).encode("utf-8")
    tabla = importar("dos.csv", contenido)
    asignadas = [f for f in tabla.filas if f.cuenta == "inventarios"]
    assert len(asignadas) == 1
    otra = next(f for f in tabla.filas if f.cuenta != "inventarios")
    assert otra.nota


def test_formato_no_soportado_se_rechaza_con_mensaje_claro():
    with pytest.raises(ValueError, match="Formato no soportado"):
        importar("balance.docx", b"lo que sea")


def test_archivo_vacio_se_rechaza():
    with pytest.raises(ValueError, match="vacio"):
        importar("balance.xlsx", b"")


def test_archivo_sin_cifras_se_rechaza():
    contenido = "Cuenta;Observacion\nEfectivo;pendiente\n".encode("utf-8")
    with pytest.raises(ValueError, match="ninguna fila con cifras"):
        importar("vacio.csv", contenido)


def test_sin_anios_en_el_encabezado_avisa_y_no_inventa():
    contenido = "Cuenta;Uno;Dos\nEfectivo;450;380\nVentas;9800;11200\n".encode("utf-8")
    tabla = importar("sin_anios.csv", contenido)
    assert tabla.periodos == ["Periodo 1", "Periodo 2"]
    assert any("no se reconocieron los anos" in a.lower() for a in tabla.avisos)


# ============================================ 4. DEL ARCHIVO AL MOTOR, ENTERO


def test_lo_importado_lo_puede_calcular_el_motor():
    """La prueba que importa: del Excel al indicador, sin digitar nada.

    Razon corriente 2024 = 5680 / 2800 = 2,0286 veces.
    """
    from motor.indicadores import calcular_todos

    tabla = importar("balance.xlsx", _excel(MATRIZ))
    datos = armar_estados(tabla.como_dict(), empresa="Importada S.A.")
    ef = EstadosFinancieros(datos)
    ind = calcular_todos(ef)

    assert ef.empresa == "Importada S.A."
    assert ef.periodos == ["2023", "2024"]
    assert ind["razon_corriente"].valores[1] == pytest.approx(5680 / 2800, abs=1e-4)
    assert ind["margen_neto"].valores[1] == pytest.approx(700 / 11200 * 100, abs=1e-4)


def test_una_fila_sin_asignar_simplemente_no_entra():
    """El motor sabe trabajar con cuentas ausentes; no hay que inventarlas."""
    cruda = {
        "periodos": ["2024"],
        "filas": [
            {"cuenta": "efectivo", "valores": [100]},
            {"cuenta": None, "valores": [999]},
            {"cuenta": "", "valores": [888]},
        ],
    }
    datos = armar_estados(cruda)
    assert datos["balance"] == {"efectivo": [100.0]}
    assert datos["resultados"] == {}


def test_si_nada_quedo_asignado_no_se_arma_un_caso_vacio():
    cruda = {"periodos": ["2024"], "filas": [{"cuenta": None, "valores": [1]}]}
    with pytest.raises(ValueError, match="Ninguna fila"):
        armar_estados(cruda)


def test_sobran_o_faltan_columnas_respecto_a_los_periodos():
    """Las cuentas se recortan o se completan con None, nunca con cero."""
    cruda = {
        "periodos": ["2023", "2024"],
        "filas": [
            {"cuenta": "efectivo", "valores": [100, 200, 300]},   # sobra una
            {"cuenta": "ventas", "valores": [900]},               # falta una
        ],
    }
    datos = armar_estados(cruda)
    assert datos["balance"]["efectivo"] == [100.0, 200.0]
    assert datos["resultados"]["ventas"] == [900.0, None]


# ================================================================ 5. PDF

def _pdf_con_tabla():
    """Un PDF con una tabla de verdad, como el que exporta un contador."""
    pytest.importorskip("reportlab")
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table

    from reportlab.lib import colors
    from reportlab.platypus import TableStyle

    buffer = io.BytesIO()
    tabla = Table(MATRIZ)
    # Con lineas: sin bordes, pdfplumber no reconoce la tabla y cae al texto,
    # que es justo la otra via y se prueba aparte.
    tabla.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))
    SimpleDocTemplate(buffer, pagesize=letter).build([tabla])
    return buffer.getvalue()


def _pdf_solo_texto():
    """Un PDF sin tabla: solo renglones de texto con las cifras al final."""
    pytest.importorskip("reportlab")
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    y = 720
    for fila in MATRIZ:
        c.drawString(60, y, str(fila[0]))
        c.drawString(340, y, str(fila[1]))
        c.drawString(440, y, str(fila[2]))
        y -= 18
    c.save()
    return buffer.getvalue()


def test_importar_pdf_con_tabla():
    tabla = importar("estados.pdf", _pdf_con_tabla())
    assert tabla.periodos == ["2023", "2024"]
    cxc = next(f for f in tabla.filas if f.cuenta == "cuentas_por_cobrar")
    assert cxc.valores == [1800.0, 2400.0]
    ventas = next(f for f in tabla.filas if f.cuenta == "ventas")
    assert ventas.valores == [9800.0, 11200.0]


def test_el_pdf_siempre_pide_revision():
    """Un PDF no guarda celdas: la tabla se reconstruye y puede salir mal.

    Por eso esta via nunca entra callada: deja un aviso pidiendo comparar
    contra el documento original antes de confirmar.
    """
    tabla = importar("estados.pdf", _pdf_con_tabla())
    assert any("pdf" in a.lower() for a in tabla.avisos)


def test_importar_pdf_sin_tablas_cae_al_texto():
    tabla = importar("texto.pdf", _pdf_solo_texto())
    assert tabla.filas
    cuentas = {f.cuenta for f in tabla.filas if f.cuenta}
    assert "cuentas_por_cobrar" in cuentas
    assert any("texto suelto" in a for a in tabla.avisos)


def test_pdf_ilegible_se_rechaza_con_mensaje_util():
    with pytest.raises(Exception) as exc:
        importar("roto.pdf", b"%PDF-1.4 esto no es un pdf de verdad")
    assert str(exc.value)


def test_del_pdf_al_indicador():
    """Recorrido completo desde un PDF: razon corriente 2024 = 5680 / 2800."""
    from motor.indicadores import calcular_todos

    tabla = importar("estados.pdf", _pdf_con_tabla())
    datos = armar_estados(tabla.como_dict(), empresa="Desde PDF S.A.")
    ind = calcular_todos(EstadosFinancieros(datos))
    assert ind["razon_corriente"].valores[1] == pytest.approx(5680 / 2800, abs=1e-4)
