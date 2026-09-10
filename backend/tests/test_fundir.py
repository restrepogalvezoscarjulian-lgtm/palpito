"""Unir los años de dos archivos de la misma empresa.

Un informe anual trae dos años: el de 2025 trae 2025 y 2024, el de 2024 trae
2024 y 2023. Juntando los dos se ven tres, que es lo que hace falta para leer
una tendencia. Con dos años solo se ve un salto.

El motor siempre supo trabajar con hasta 6 periodos -el caso andina_trienio
corre con tres-, pero el cargador solo aceptaba un archivo. La casa tenia tres
pisos y la escalera llegaba al primero.
"""

import pytest

from motor.importacion import MAX_PERIODOS, fundir_estados

INFORME_2024 = {
    "empresa": "Cementos Ejemplo S.A.", "moneda": "COP", "unidad": "millones",
    "periodos": ["2023", "2024"],
    "balance": {"efectivo": [100, 200], "activo_total": [1000, 1100]},
    "resultados": {"ventas": [5000, 5500]},
}

INFORME_2025 = {
    "empresa": "Cementos Ejemplo S.A.", "moneda": "COP", "unidad": "millones",
    "periodos": ["2024", "2025"],
    # 2024 viene REEXPRESADO: 210 en vez de 200. Pasa de verdad.
    "balance": {"efectivo": [210, 300], "activo_total": [1120, 1300]},
    "resultados": {"ventas": [5480, 6100], "costo_ventas": [3000, 3400]},
}


def test_dos_informes_de_dos_anios_dan_tres_anios():
    u = fundir_estados(INFORME_2024, INFORME_2025)
    assert u["periodos"] == ["2023", "2024", "2025"]
    assert u["fusion"]["agregados"] == ["2025"]
    assert u["fusion"]["repetidos"] == ["2024"]


def test_los_anios_quedan_en_orden_cronologico():
    """Al reves tambien: primero el informe nuevo, despues el viejo."""
    u = fundir_estados(INFORME_2025, INFORME_2024)
    assert u["periodos"] == ["2023", "2024", "2025"]


@pytest.mark.parametrize("conservar,esperado", [("base", 200), ("nuevo", 210)])
def test_el_anio_repetido_lo_decide_el_usuario(conservar, esperado):
    """Las empresas reexpresan cifras de un informe al siguiente. Elegir en
    silencio seria inventar; promediar, peor.
    """
    u = fundir_estados(INFORME_2024, INFORME_2025, conservar=conservar)
    assert u["balance"]["efectivo"] == [100, esperado, 300]


def test_una_cuenta_que_solo_trae_un_archivo_no_se_pierde():
    """costo_ventas solo esta en el informe de 2025: los años que no lo traen
    quedan en None, nunca en cero.
    """
    u = fundir_estados(INFORME_2024, INFORME_2025)
    assert u["resultados"]["costo_ventas"] == [None, 3000, 3400]


def test_nunca_se_promedian_dos_versiones_del_mismo_anio():
    u = fundir_estados(INFORME_2024, INFORME_2025, conservar="base")
    assert u["balance"]["efectivo"][1] in (200, 210), "salio un promedio"
    assert u["balance"]["efectivo"][1] == 200


def test_la_fusion_queda_anotada_donde_el_usuario_la_lea():
    u = fundir_estados(INFORME_2024, INFORME_2025, conservar="nuevo")
    avisos = " ".join(u["supuestos"]["ajustes_importacion"])
    assert "2025" in avisos and "segundo archivo" in avisos
    assert "2024" in avisos and "reexpresan" in avisos
    assert "el de el" not in avisos, "quedo mal redactado"


def test_dos_empresas_distintas_se_unen_pero_con_advertencia():
    """No se bloquea -a veces el nombre viene del archivo y esta mal escrito-
    pero tiene que quedar dicho.
    """
    otra = dict(INFORME_2025, empresa="Otra Cosa S.A.")
    u = fundir_estados(INFORME_2024, otra)
    avisos = " ".join(u["supuestos"]["ajustes_importacion"])
    assert "nombres distintos" in avisos


def test_monedas_distintas_avisan_que_no_son_comparables():
    otra = dict(INFORME_2025, moneda="USD")
    u = fundir_estados(INFORME_2024, otra)
    avisos = " ".join(u["supuestos"]["ajustes_importacion"])
    assert "NO son comparables" in avisos


def test_no_se_pasa_del_maximo_de_periodos():
    """Si sobran, se conservan los mas recientes: son los que sirven para
    proyectar.
    """
    viejo = {"empresa": "X", "periodos": [str(a) for a in range(2016, 2024)],
             "balance": {"efectivo": list(range(8))}, "resultados": {}}
    u = fundir_estados(viejo, INFORME_2025)
    assert len(u["periodos"]) == MAX_PERIODOS
    assert u["periodos"][-1] == "2025"


def test_un_encabezado_sucio_no_revienta_el_orden():
    """El consolidado de Grupo Bolivar produce periodos como "de 2025 de"."""
    sucio = {"empresa": "X", "periodos": ["de 2025 de", "2024"],
             "balance": {"efectivo": [1, 2]}, "resultados": {}}
    limpio = {"empresa": "X", "periodos": ["2023"],
              "balance": {"efectivo": [3]}, "resultados": {}}
    u = fundir_estados(sucio, limpio)
    assert u["periodos"][0] == "2023"
    assert u["periodos"][-1] == "de 2025 de"


def test_sin_periodos_se_rechaza():
    with pytest.raises(ValueError):
        fundir_estados({"periodos": []}, INFORME_2025)


def test_una_eleccion_invalida_se_rechaza():
    with pytest.raises(ValueError):
        fundir_estados(INFORME_2024, INFORME_2025, conservar="promedio")
