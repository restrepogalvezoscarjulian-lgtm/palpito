"""Pruebas del detector de páginas de estados financieros.

Es deterministico a proposito: no usa el modelo de lenguaje. Un estado
financiero siempre se anuncia con las mismas palabras, y buscarlas se puede
auditar renglon por renglon.
"""

import pytest

from motor.secciones import MAX_SEPARACION, analizar_paginas

BALANCE = """Grupo Ejemplo S.A.
Estado de Situación Financiera Consolidado
Al 31 de diciembre (Valores expresados en millones de pesos)
ACTIVO
Activo corriente
Efectivo y equivalentes de efectivo 8 $ 3.195.196 $ 1.128.399
Inventarios, neto 11 2.558.764 2.447.873
Total activo corriente $ 8.817.990 $ 6.416.225
Total activos $ 27.419.325 $ 16.942.462
Total pasivo corriente 4.473.368 3.701.407
Total patrimonio 5.416.711 7.118.853
"""

RESULTADOS = """Grupo Ejemplo S.A.
Estado de Resultados Consolidado
Ingresos operacionales 20.578.988 18.589.956
Costos de ventas ( 12.457.813) ( 11.304.753)
Utilidad bruta 8.121.175 7.285.203
Utilidad neta del periodo 1.245.336 765.354
"""

INDICE = """Contenido
Estados de situación financiera consolidados ........................................ 4
Estados de resultados consolidados .................................................. 5
Estados de flujos de efectivo consolidados .......................................... 8
1. Entidad reportante ............................................................... 9
Total activos ...................................................................... 12
"""

NOTA = """Nota 14. Propiedades, planta y equipo
El saldo corresponde a los activos productivos del grupo. Durante el periodo
se registraron adiciones por 450.000 y retiros por 12.000.
"""

RELLENO = "Texto de relleno sin marcadores financieros.\n"


# ------------------------------------------------------------ deteccion basica


def test_encuentra_el_balance_y_los_resultados_seguidos():
    paginas = [RELLENO] * 9 + [BALANCE, RESULTADOS] + [NOTA] * 5
    r = analizar_paginas(paginas)
    assert r["encontrado"] is True
    assert r["paginas"].startswith("10-")
    assert "página 10" in r["lectura"]
    assert "página 11" in r["lectura"]


def test_el_indice_no_gana_aunque_nombre_todos_los_estados():
    """Un indice menciona los estados y dispararia todos los marcadores."""
    paginas = [RELLENO] * 8 + [INDICE, BALANCE, RESULTADOS]
    r = analizar_paginas(paginas)
    assert 9 in r["descartados_por_indice"]
    assert r["paginas"].startswith("10")


def test_una_nota_suelta_no_se_confunde_con_un_estado():
    r = analizar_paginas([RELLENO] * 5 + [NOTA] * 5)
    assert r["encontrado"] is False


def test_sin_nada_reconocible_lo_dice_en_vez_de_inventar():
    r = analizar_paginas([RELLENO] * 20)
    assert r["encontrado"] is False
    assert r["paginas"] == ""
    assert "No se reconocieron" in r["lectura"]


def test_un_documento_vacio_no_revienta():
    assert analizar_paginas([])["encontrado"] is False
    assert analizar_paginas(["", "   ", None or ""])["encontrado"] is False


# ------------------------------------------------- la regla de proximidad


def test_candidatos_dispersos_no_producen_un_rango_gigante():
    """El caso Ecopetrol: los estados van escaneados y solo se ven notas.

    Antes proponia "36-126", noventa paginas, que es peor que no acotar.
    """
    paginas = [RELLENO] * 30 + [NOTA] + [RELLENO] * 90 + [RESULTADOS] + [RELLENO] * 5
    r = analizar_paginas(paginas)
    if r["encontrado"]:
        ini, _, fin = r["paginas"].partition("-")
        ancho = int(fin or ini) - int(ini)
        assert ancho <= MAX_SEPARACION + 1, f"rango demasiado ancho: {r['paginas']}"


def test_dos_debiles_y_lejanos_se_reportan_como_no_encontrado():
    debil_balance = "Total activo\nActivo corriente\nPasivo corriente\n"
    debil_result = "Utilidad bruta\nUtilidad neta\ncosto de ventas\n"
    paginas = [debil_balance] + [RELLENO] * 60 + [debil_result]
    r = analizar_paginas(paginas)
    assert r["encontrado"] is False
    assert r.get("disperso") is True


def test_estados_juntos_no_se_marcan_como_dispersos():
    paginas = [RELLENO] * 9 + [BALANCE, RESULTADOS]
    assert analizar_paginas(paginas).get("disperso") is False


# ------------------------------------- un estado repartido en varias hojas

# El caso Grupo Argos: el balance ocupa tres paginas, cada una repitiendo el
# titulo, y ninguna trae los totales completos.
ARGOS_ACTIVOS = """Grupo Argos S.A.
Estado de Situación Financiera Consolidado
ACTIVOS
Activo corriente
Efectivo y equivalentes de efectivo 5 1.897.406 2.084.372
Total activos 48.012.775 46.220.109
"""

ARGOS_PASIVOS = """Grupo Argos S.A.
Estado de Situación Financiera Consolidado
PASIVOS
Pasivo corriente
Obligaciones financieras 2.945.325 3.118.004
Total pasivos 21.398.531 22.110.442
"""

ARGOS_PATRIMONIO = """Grupo Argos S.A.
Estado de Situación Financiera Consolidado
PATRIMONIO
Total patrimonio 26.614.244 24.109.667
Total pasivos y patrimonio 48.012.775 46.220.109
"""

# Una nota del fondo del documento que los menciona todos de una vez. Puntua
# mas que cualquiera de las tres hojas de arriba por separado.
NOTA_FUERTE = """Nota 22. Información por segmentos
Estado de Situación Financiera por segmento operativo
Total activos 48.012.775 Total pasivos 21.398.531
Total activo corriente 9.114.220 Total pasivo corriente 7.882.104
"""


def test_un_balance_de_tres_hojas_le_gana_a_una_nota_concentrada():
    """Argos: puntuando hojas sueltas, la nota de la 82 se llevaba el balance.

    Ninguna de las tres hojas del balance verdadero alcanza sola el puntaje de
    la nota. Sumadas como un bloque, si.
    """
    paginas = (
        [RELLENO] * 15
        + [ARGOS_ACTIVOS, ARGOS_PASIVOS, ARGOS_PATRIMONIO, RESULTADOS]
        + [RELLENO] * 60
        + [NOTA_FUERTE]
        + [RELLENO] * 5
    )
    r = analizar_paginas(paginas)
    assert r["encontrado"] is True
    assert r["paginas"] == "16-19", "se perdio el activo entero"
    assert r.get("disperso") is False


def test_el_bloque_elegido_queda_por_escrito():
    """Hay que poder discutir por que el bloque le gano a la nota."""
    paginas = (
        [RELLENO] * 15
        + [ARGOS_ACTIVOS, ARGOS_PASIVOS, ARGOS_PATRIMONIO, RESULTADOS]
        + [RELLENO] * 60
        + [NOTA_FUERTE]
    )
    bloques = analizar_paginas(paginas)["bloques"]
    balance = next(b for b in bloques if b["clase"] == "balance")
    assert balance["paginas"] == [16, 17, 18]
    nota_sola = analizar_paginas([NOTA_FUERTE])["detalle"][0]["puntaje"]
    assert balance["puntaje"] > nota_sola


def test_se_elige_la_pareja_vecina_no_el_mejor_de_cada_clase():
    """Los estados van juntos: un balance sin resultados al lado es una nota."""
    paginas = (
        [RELLENO] * 4
        + [BALANCE, RESULTADOS]
        + [RELLENO] * 40
        + [NOTA_FUERTE, NOTA_FUERTE]
        + [RELLENO] * 5
    )
    r = analizar_paginas(paginas)
    assert r["paginas"].startswith("5"), r["paginas"]


def test_la_lectura_menciona_las_tres_hojas_del_balance():
    paginas = [RELLENO] * 15 + [
        ARGOS_ACTIVOS, ARGOS_PASIVOS, ARGOS_PATRIMONIO, RESULTADOS]
    assert "páginas 16 a 18" in analizar_paginas(paginas)["lectura"]


# ----------------------------------------------------------- auditabilidad


def test_el_resultado_explica_por_que_eligio_esas_paginas():
    """El detector tiene que poder discutirse, igual que un indicador."""
    paginas = [RELLENO] * 9 + [BALANCE, RESULTADOS]
    r = analizar_paginas(paginas)
    assert r["detalle"], "no reporto evidencia"
    top = r["detalle"][0]
    assert top["pagina"] in (10, 11)
    assert top["marcadores"]
    assert top["puntaje"] > 0


def test_reconoce_los_nombres_alternos_del_balance():
    for titulo in ("Balance General", "Estado de Posición Financiera",
                   "ESTADO DE SITUACIÓN FINANCIERA"):
        cuerpo = f"{titulo}\nTotal activo 100\nTotal pasivo 40\nTotal patrimonio 60\n"
        r = analizar_paginas([RELLENO, cuerpo, RESULTADOS])
        assert r["encontrado"] is True, titulo


# ------------------- prosa que menciona los estados (Grupo Bolivar 2024)

# El titulo real que trae un informe consolidado: con una palabra en la mitad.
BALANCE_CONSOLIDADO = """Grupo Ejemplo S.A. Y Subsidiarias
Estado Consolidado de Situación Financiera
(Millones de pesos colombianos)
Efectivo y equivalentes de efectivo 13 16.688.209 15.470.751
Total activo 203.007.173 190.114.552
Total pasivo 183.859.259 172.010.121
Total patrimonio 19.147.914 18.104.431
"""

# Una nota en prosa. Menciona los estados por su nombre -como hace toda nota
# contable- pero no trae un solo saldo.
NOTA_QUE_MENCIONA = """NOTAS A LOS ESTADOS FINANCIEROS CONSOLIDADOS 2024
La ganancia o pérdida generada se reconoce en el estado de resultados del
periodo en que ocurre. Los activos que cumplen las condiciones se presentan
en el estado de situación financiera al cierre.
"""


def test_un_titulo_con_una_palabra_en_la_mitad_se_reconoce():
    """"Estado CONSOLIDADO de Situación Financiera". Buscando la frase seguida,
    el estado verdadero sacaba cero puntos de titulo.
    """
    r = analizar_paginas([RELLENO] * 13 + [BALANCE_CONSOLIDADO, RESULTADOS])
    assert r["encontrado"] is True
    assert r["paginas"].startswith("14"), r["paginas"]


def test_la_prosa_de_las_notas_no_le_gana_al_estado_verdadero():
    """El caso Grupo Bolivar 2024: tres paginas seguidas de notas decian "se
    reconoce en el estado de resultados" y sumaban 12 puntos como bloque,
    contra los 4 del balance verdadero de la pagina 14.

    Sumar prosa no hace un estado financiero: solo las paginas con renglones de
    saldo forman bloque.
    """
    paginas = (
        [RELLENO] * 13
        + [BALANCE_CONSOLIDADO, RESULTADOS]
        + [RELLENO] * 48
        + [NOTA_QUE_MENCIONA] * 3
        + [RELLENO] * 5
    )
    r = analizar_paginas(paginas)
    assert r["paginas"] == "14-15", f"eligio las notas: {r['paginas']}"


def test_una_nota_suelta_no_forma_bloque_con_la_siguiente():
    bloques = analizar_paginas(
        [RELLENO] * 13 + [BALANCE_CONSOLIDADO, RESULTADOS]
        + [RELLENO] * 20 + [NOTA_QUE_MENCIONA] * 4
    )["bloques"]
    for b in bloques:
        assert len(b["paginas"]) == 1 or min(b["paginas"]) < 20, b
