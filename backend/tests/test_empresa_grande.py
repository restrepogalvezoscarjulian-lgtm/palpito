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


# ------------------------- cuentas que se llaman casi igual (Grupo Argos 2025)


@pytest.mark.parametrize("etiqueta", [
    "Activos por impuestos",
    "Activos por impuestos corrientes",
    "Pasivos por impuestos",
    "Impuestos por pagar",
    "Impuesto diferido",
])
def test_un_saldo_del_balance_no_puede_caer_en_resultados(etiqueta):
    """El caso Argos: "Activos por impuestos" (257.927) entraba como el gasto
    de renta del periodo, que eran 589.725. La tasa efectiva salio 19,49%
    cuando el propio informe declara 44,57%. Nada fallo: la cifra era otra.
    """
    from motor.importacion import CUENTAS_RESULTADOS, buscar_cuenta
    cuenta, _ = buscar_cuenta(etiqueta)
    assert cuenta not in CUENTAS_RESULTADOS, f"{etiqueta} se colo como {cuenta}"


@pytest.mark.parametrize("etiqueta", [
    "Impuesto sobre las ganancias",
    "Impuesto a las ganancias",
    "Impuesto de renta",
    "Gasto por impuestos",
])
def test_el_gasto_de_renta_si_se_reconoce_por_su_nombre_publicado(etiqueta):
    from motor.importacion import buscar_cuenta
    assert buscar_cuenta(etiqueta)[0] == "impuestos"


# ------------------------------ deuda financiera contra pasivo no corriente


def test_el_total_de_pasivos_no_corrientes_no_es_deuda_financiera():
    """En Argos ese total eran 12.492.908 y la deuda real 7.503.420: 66% de
    sobrestimacion. El total incluye impuesto diferido, provisiones y cuentas
    por pagar de largo plazo, que no cuestan intereses.
    """
    from motor.importacion import buscar_cuenta
    for etiqueta in ("Total pasivos no corrientes", "Pasivo no corriente",
                     "TOTAL PASIVOS NO CORRIENTES"):
        assert buscar_cuenta(etiqueta)[0] != "deuda_financiera_lp", etiqueta


def test_la_deuda_se_reparte_segun_de_que_lado_del_corte_cayo():
    """"Obligaciones financieras" aparece dos veces en la misma pagina, con el
    mismo nombre: solo la posicion dice cual es cual.
    """
    from motor.importacion import Fila, Tabla, mapear

    tabla = Tabla(periodos=["2025", "2024"], filas=[
        Fila("Obligaciones financieras", [1777080, 2171508]),
        Fila("Bonos e instrumentos financieros compuestos", [405808, 731549]),
        Fila("TOTAL PASIVOS CORRIENTES PASIVOS NO CORRIENTES", [5580106, 8266843]),
        Fila("Obligaciones financieras", [2945325, 3356071]),
        Fila("Impuesto diferido", [2720397, 1804928]),
        Fila("Bonos e instrumentos financieros compuestos", [4558095, 5144207]),
        Fila("TOTAL PASIVOS NO CORRIENTES", [12492908, 11030737]),
    ])
    cuentas = [f.cuenta for f in mapear(tabla).filas]
    assert cuentas == [
        "deuda_financiera_cp", "deuda_financiera_cp", "pasivo_corriente",
        "deuda_financiera_lp", None, "deuda_financiera_lp", "pasivo_no_corriente",
    ], cuentas
    # Lo importante sigue en pie: el TOTAL de pasivos no corrientes (12.492.908)
    # no puede confundirse con la deuda financiera (7.503.420). Ahora tiene su
    # propia cuenta en vez de perderse, que es lo que hacia que ningun balance
    # real cuadrara.
    assert tabla.filas[-1].cuenta != "deuda_financiera_lp"


def test_el_renglon_pegado_conserva_el_significado_del_principio():
    """El lector de PDF pega el encabezado siguiente al total anterior. Una
    etiqueta dice lo que dice por como EMPIEZA; lo de atras es ruido.
    """
    from motor.importacion import buscar_cuenta

    assert buscar_cuenta("TOTAL PASIVOS CORRIENTES PASIVOS NO CORRIENTES")[0] \
        == "pasivo_corriente"
    assert buscar_cuenta("TOTAL ACTIVOS CORRIENTES ACTIVOS NO CORRIENTES")[0] \
        == "activo_corriente"


def test_el_total_de_pasivos_tiene_su_propia_cuenta():
    """Sin ella, el motor armaba el pasivo total sumando lo que encontrara y
    NINGUN balance de una empresa real cuadraba. En Almacenes Exito 2024 el
    "Total pasivo" (9.539.043) estaba en el PDF sin asignar: con el patrimonio
    da 17.554.555, que es exactamente el activo total declarado.
    """
    from motor.importacion import buscar_cuenta

    for etiqueta in ("Total pasivo", "TOTAL PASIVOS", "Total de pasivos",
                     "Pasivos totales"):
        assert buscar_cuenta(etiqueta)[0] == "pasivo_total", etiqueta
    for etiqueta in ("Total pasivo no corriente", "TOTAL PASIVOS NO CORRIENTES"):
        assert buscar_cuenta(etiqueta)[0] == "pasivo_no_corriente", etiqueta


def test_la_deuda_repartida_en_varios_renglones_se_suma_y_se_anota():
    """Obligaciones financieras + bonos. Sumar en silencio seria peor que no
    sumar: el ajuste queda anotado en los supuestos.
    """
    from motor.importacion import armar_estados

    cruda = {
        "periodos": ["2025", "2024"],
        "filas": [
            {"cuenta": "deuda_financiera_lp", "valores": [2945325, 3356071]},
            {"cuenta": "deuda_financiera_lp", "valores": [4558095, 5144207]},
        ],
    }
    datos = armar_estados(cruda, empresa="Grupo Argos")
    assert datos["balance"]["deuda_financiera_lp"] == [7503420, 8500278]
    ajustes = " ".join(datos["supuestos"]["ajustes_importacion"])
    assert "deuda_financiera_lp" in ajustes and "2 renglones" in ajustes


# ---------------------------------- que la deuda no se coma lo que no es deuda


@pytest.mark.parametrize("etiqueta", [
    "Inversiones en bonos",
    "Activos financieros",
    "Instrumentos financieros derivados",
    "Cuentas por cobrar por bonos",
])
def test_un_bono_que_se_tiene_no_se_cuenta_como_deuda(etiqueta):
    """Un bono se puede deber o se puede tener. Confundirlos le invierte el
    signo al endeudamiento de la empresa.
    """
    from motor.importacion import buscar_cuenta
    cuenta, _ = buscar_cuenta(etiqueta)
    assert cuenta not in ("deuda_financiera_cp", "deuda_financiera_lp"), etiqueta


def test_un_total_mayor_devuelve_la_marca_a_corriente():
    """Si un balance no declara el subtotal de activos no corrientes, la marca
    se quedaria puesta y los pasivos corrientes de mas abajo entrarian como
    deuda de largo plazo.
    """
    from motor.importacion import Fila, Tabla, mapear

    tabla = Tabla(periodos=["2025"], filas=[
        Fila("Total activos corrientes", [100]),
        Fila("Propiedades planta y equipo", [200]),
        Fila("TOTAL ACTIVOS", [300]),
        Fila("Obligaciones financieras", [50]),
    ])
    assert mapear(tabla).filas[-1].cuenta == "deuda_financiera_cp"


def test_tres_renglones_de_deuda_producen_un_solo_aviso():
    from motor.importacion import armar_estados

    datos = armar_estados({"periodos": ["2025"], "filas": [
        {"cuenta": "deuda_financiera_lp", "valores": [100]},
        {"cuenta": "deuda_financiera_lp", "valores": [200]},
        {"cuenta": "deuda_financiera_lp", "valores": [300]},
    ]})
    assert datos["balance"]["deuda_financiera_lp"] == [600]
    avisos = [a for a in datos["supuestos"]["ajustes_importacion"]
              if "deuda_financiera_lp" in a]
    assert len(avisos) == 1, avisos
    assert "3 renglones" in avisos[0]


def test_la_pagina_de_mas_metia_las_operaciones_discontinuadas():
    """El detector se queda en 16-19 a proposito. La 20 trae el resultado
    integral, y con ella la utilidad neta pasaba de 733.427 (operaciones
    continuadas) a 4.346.462, que incluye la venta de Summit Materials y la
    escision de Grupo Sura: plata que no se repite y no sirve para proyectar.
    """
    from motor.secciones import analizar_paginas

    balance = ("Estado de Situación Financiera\nTotal activos 100\n"
               "Total pasivos 40\nTotal patrimonio 60\n")
    resultados = ("Estado de Resultados\nUtilidad bruta 30\n"
                  "Utilidad operacional 20\nUtilidad neta 10\ncosto de ventas 5\n")
    integral = "Utilidad neta del periodo 40\nGanancia neta por conversion 30\n"

    relleno = "Texto sin marcadores financieros.\n"
    r = analizar_paginas([relleno] * 15 + [balance, resultados, integral])
    assert r["paginas"] == "16-17", "se colo la hoja del resultado integral"


# ------------------- la utilidad neta que sirve para proyectar (Grupo Argos)


@pytest.mark.parametrize("etiqueta", [
    "UTILIDAD NETA OPERACIONES DISCONTINUADAS",
    "Utilidad antes de impuestos operaciones discontinuadas",
    "OTRO RESULTADO INTEGRAL, NETO DE IMPUESTOS",
    "RESULTADO INTEGRAL TOTAL",
])
def test_lo_discontinuado_y_el_integral_no_son_ninguna_cuenta(etiqueta):
    """Plata de vender un negocio, y revaluaciones que no pasaron por el
    estado de resultados. Ninguna de las dos cosas es una de las 23 cuentas.
    """
    from motor.importacion import buscar_cuenta
    assert buscar_cuenta(etiqueta)[0] is None, etiqueta


@pytest.mark.parametrize("primero", [True, False])
def test_la_continuada_le_gana_al_total_sin_importar_el_orden(primero):
    """Hasta hoy la continuada ganaba solo por aparecer antes en la pagina, y
    el renglon pelado "UTILIDAD NETA" la desplazaba por coincidencia exacta.
    """
    from motor.importacion import Fila, Tabla, mapear

    continuada = Fila("UTILIDAD NETA OPERACIONES CONTINUADAS", [733427, 160652])
    total = Fila("UTILIDAD NETA", [4346462, 7646799])
    filas = [continuada, total] if primero else [total, continuada]

    mapear(Tabla(periodos=["2025", "2024"], filas=filas))
    assert continuada.cuenta == "utilidad_neta"
    assert total.cuenta is None


def test_leer_una_hoja_de_mas_ya_no_cambia_la_utilidad_neta():
    """La prueba de fondo. El estado de resultados de Argos va en la 19 y el
    resultado integral en la 20. Antes, incluir la 20 subia la utilidad neta
    de 733.427 a 4.346.462 sin que nada avisara: se colaban la venta de Summit
    Materials y la escision de Grupo Sura.
    """
    from motor.importacion import Fila, Tabla, armar_estados, mapear

    pagina19 = [
        Fila("UTILIDAD BRUTA", [3438340, 3120150]),
        Fila("UTILIDAD ANTES DE IMPUESTOS", [1323152, 457735]),
        Fila("Impuesto sobre las ganancias", [-589725, -297083]),
        Fila("UTILIDAD NETA OPERACIONES CONTINUADAS", [733427, 160652]),
        Fila("UTILIDAD NETA OPERACIONES DISCONTINUADAS", [3613035, 7486147]),
    ]
    pagina20 = [
        Fila("UTILIDAD NETA", [4346462, 7646799]),
        Fila("OTRO RESULTADO INTEGRAL, NETO DE IMPUESTOS", [-3518205, 428315]),
        Fila("RESULTADO INTEGRAL TOTAL", [828257, 8075114]),
    ]

    def leer(filas):
        tabla = mapear(Tabla(periodos=["2025", "2024"], filas=[
            Fila(f.etiqueta, list(f.valores)) for f in filas]))
        return armar_estados(tabla.como_dict(), empresa="Grupo Argos")

    solo19 = leer(pagina19)
    con20 = leer(pagina19 + pagina20)

    assert solo19["resultados"]["utilidad_neta"] == [733427, 160652]
    assert con20["resultados"]["utilidad_neta"] == [733427, 160652]
    # y la hoja de mas tampoco puede tocar el gasto de renta
    assert con20["resultados"]["impuestos"] == [589725, 297083]


def test_el_motor_dice_que_dejo_fuera_lo_discontinuado():
    """La decision es intencional, asi que tiene que quedar por escrito donde
    el usuario la lea, no solo en el codigo.
    """
    from motor.importacion import armar_estados

    datos = armar_estados({"periodos": ["2025", "2024"], "filas": [
        {"cuenta": "utilidad_neta",
         "etiqueta": "UTILIDAD NETA OPERACIONES CONTINUADAS",
         "valores": [733427, 160652]},
        {"cuenta": None,
         "etiqueta": "UTILIDAD NETA OPERACIONES DISCONTINUADAS",
         "valores": [3613035, 7486147]},
    ]}, empresa="Grupo Argos")

    avisos = datos["supuestos"]["ajustes_importacion"]
    aviso = next((a for a in avisos if "utilidad_neta" in a), None)
    assert aviso, avisos
    assert "operaciones continuadas" in aviso
    assert "3.613.035" in aviso, "no nombro la cifra que quedo fuera"


def test_una_pyme_no_ve_avisos_que_no_le_incumben():
    """No tiene operaciones discontinuadas: el aviso no debe aparecer."""
    from motor.importacion import armar_estados

    datos = armar_estados({"periodos": ["2024"], "filas": [
        {"cuenta": "utilidad_neta", "etiqueta": "Utilidad neta", "valores": [120]},
    ]})
    assert "supuestos" not in datos


# ------------------------------------------------ la utilidad bajo NIIF
#
# El 10-sep-2026 el ensayo de la exposicion mostro a Almacenes Exito con
# Rentabilidad y Generacion de valor en "sin datos": el 40% del puntaje de
# salud sin evaluar, y nada habia fallado. Faltaban utilidad_operacional y
# utilidad_neta, y las dos venian legibles en el PDF.
#
# La causa fue una guarda nuestra: para que los renglones del flujo de efectivo
# no se disfrazaran de resultados se prohibio toda etiqueta que contuviera
# "actividades de operacion" -y asi se llama, bajo NIIF, la utilidad
# operacional-. Estas pruebas fijan LAS DOS MITADES: la que debe entrar y la
# que debe seguir fuera. Sin la segunda, "arreglar" la primera reabre el hueco
# de los dias de inventario en 3.614.


@pytest.mark.parametrize("etiqueta,cuenta", [
    ("Ganancia por actividades de operación", "utilidad_operacional"),
    ("GANANCIA POR ACTIVIDADES DE OPERACION", "utilidad_operacional"),
    ("Utilidad por actividades de operación", "utilidad_operacional"),
    ("Ganancia del año", "utilidad_neta"),
    ("Ganancia del periodo", "utilidad_neta"),
    ("Utilidad del año", "utilidad_neta"),
])
def test_la_utilidad_niif_entra_aunque_nombre_las_actividades_de_operacion(etiqueta, cuenta):
    """Un renglon que EMPIEZA por "ganancia" es un resultado del periodo."""
    assert buscar_cuenta(etiqueta)[0] == cuenta


@pytest.mark.parametrize("etiqueta", [
    "Efectivo neto de actividades de operación",
    "Flujos de efectivo netos de actividades de operación",
    "Efectivo neto usado en actividades de inversión",
    "Efectivo neto provisto por actividades de financiación",
    "Resultado operacional antes de cambios en el capital de trabajo",
])
def test_el_flujo_de_efectivo_sigue_sin_pasar_por_resultado(etiqueta):
    """La otra mitad: lo que la guarda existe para atajar."""
    assert buscar_cuenta(etiqueta)[0] is None


def test_la_ganancia_del_ano_gana_aunque_traiga_pegado_el_encabezado():
    """El lector de PDF entrega "Ganancia del ano Ganancia por accion (*)".

    Manda como EMPIEZA la etiqueta; lo de atras es el encabezado siguiente.
    """
    assert buscar_cuenta("Ganancia del año Ganancia por acción (*)")[0] == "utilidad_neta"
    assert buscar_cuenta("Ganancia del año Ganancia atribuible a:")[0] == "utilidad_neta"


def test_el_otro_resultado_integral_no_es_la_utilidad_del_ano():
    """Revaluaciones que no pasaron por el estado de resultados."""
    assert buscar_cuenta("Ganancia del año Otro resultado integral")[0] is None
    assert buscar_cuenta("Resultado integral total")[0] is None


def test_la_ganancia_antes_de_impuestos_no_se_confunde_con_la_operacional():
    """Las dos empiezan por "ganancia por"; separan en la tercera palabra."""
    antes = "Ganancia por operaciones continuadas antes del impuesto a las ganancias"
    assert buscar_cuenta(antes)[0] == "utilidad_antes_impuestos"
    assert buscar_cuenta("Ganancia por actividades de operación")[0] == "utilidad_operacional"


# ------------------------------------------------ el encadenamiento y el catalogo
#
# Al entrar utilidad_antes_impuestos (10-sep-2026) aparecieron 3 ERRORES contra
# Almacenes Exito y el dictamen paso a decir "Puntaje no confiable". Los
# estados de Exito estan bien: entre la utilidad operacional y la de antes de
# impuestos van ingresos financieros, metodo de participacion y otras ganancias
# netas -96.464 en 2024- que las 23 cuentas no recogen.
#
# La regla que quedo: si el catalogo NO explica el activo, esos dos eslabones
# son ADVERTENCIA; si SI lo explica -una pyme-, siguen siendo ERROR. Las dos
# mitades van fijadas, porque degradar de mas seria tapar descuadres de verdad.


def _ef(**cuentas):
    """Un periodo, cifras sueltas. Cada cuenta viaja como lista de un valor."""
    from motor.modelos import EstadosFinancieros
    del_balance = ("activo_corriente", "propiedad_planta_equipo", "activo_total")
    balance = {k: [v] for k, v in cuentas.items() if k in del_balance}
    resultados = {k: [v] for k, v in cuentas.items() if k not in del_balance}
    return EstadosFinancieros({"empresa": "Prueba", "periodos": ["2024"],
                               "balance": balance, "resultados": resultados})


def _cadena(hallazgos):
    return [h for h in hallazgos if h.codigo == "CADENA_RESULTADOS"]


def test_en_una_pyme_el_descuadre_de_la_cadena_sigue_siendo_error():
    """El activo cuadra con el catalogo: aqui un descuadre es un descuadre."""
    ef = _ef(activo_corriente=600, propiedad_planta_equipo=400, activo_total=1000,
             utilidad_operacional=200, gastos_financieros=50,
             utilidad_antes_impuestos=900)          # deberia dar 150
    h = _cadena(validar(ef))
    assert h, "no detecto el descuadre"
    assert all(x.severidad == "error" for x in h), [x.severidad for x in h]


def test_en_una_empresa_grande_el_mismo_descuadre_es_advertencia():
    """Quedan activos fuera del detalle: el catalogo no explica esta empresa."""
    ef = _ef(activo_corriente=600, propiedad_planta_equipo=400, activo_total=5000,
             utilidad_operacional=200, gastos_financieros=50,
             utilidad_antes_impuestos=900)
    h = _cadena(validar(ef))
    assert h, "no detecto el descuadre"
    assert all(x.severidad == "advertencia" for x in h), [x.severidad for x in h]
    assert "catálogo" in h[0].detalle, "no explico por que se degrado"
    assert "750" in h[0].detalle, "no nombro la diferencia"


def test_ventas_menos_costo_es_error_aunque_la_empresa_sea_grande():
    """Ese eslabon no admite partidas intermedias: es aritmetica cerrada."""
    ef = _ef(activo_corriente=600, propiedad_planta_equipo=400, activo_total=5000,
             ventas=1000, costo_ventas=600, utilidad_bruta=900)   # deberia dar 400
    h = _cadena(validar(ef))
    assert h, "no detecto el descuadre"
    assert h[0].severidad == "error", h[0].severidad


def test_la_utilidad_neta_es_error_aunque_la_empresa_sea_grande():
    """Antes de impuestos menos impuestos tampoco admite intermedias."""
    ef = _ef(activo_corriente=600, propiedad_planta_equipo=400, activo_total=5000,
             utilidad_antes_impuestos=500, impuestos=100, utilidad_neta=900)
    h = _cadena(validar(ef))
    assert h, "no detecto el descuadre"
    assert h[0].severidad == "error", h[0].severidad


def test_una_cadena_que_cuadra_no_reporta_nada():
    ef = _ef(activo_corriente=600, propiedad_planta_equipo=400, activo_total=5000,
             utilidad_operacional=200, gastos_financieros=50,
             utilidad_antes_impuestos=150)
    assert not _cadena(validar(ef))
