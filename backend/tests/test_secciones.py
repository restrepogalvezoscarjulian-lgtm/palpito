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
