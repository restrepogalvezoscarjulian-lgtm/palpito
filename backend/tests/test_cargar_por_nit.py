"""Cargar una empresa por su nombre, sin PDF.

Ninguna prueba toca internet: `traer` se inyecta de mentira. Los conceptos y
las cifras imitan lo que el portal devolvio para D1 S.A.S. el 11-sep-2026.
"""

import pytest

from herramientas.supersociedades import (
    CONCEPTOS_SUMADOS,
    DATASET_BALANCE,
    DATASET_RESULTADOS,
    anios_con_balance,
    buscar_empresas,
    descargar_empresa,
    texto_de_busqueda,
    url_buscar_empresas,
    url_cortes,
)


# ---------------------------------------------------------------- busqueda


def test_el_texto_va_en_mayusculas_y_sin_lo_que_rompe_la_consulta():
    assert texto_de_busqueda("  d1   s.a.s ") == "D1 S.A.S"
    # comillas y comodines del LIKE no viajan: los escribiria alguien
    # con malas intenciones, no un usuario buscando su empresa
    assert texto_de_busqueda("d1' or '1'='1") == "D1 OR 1=1"
    assert "%" not in texto_de_busqueda("50%")


def test_las_tildes_del_usuario_se_caen_como_en_el_directorio():
    """El directorio escribe ALMACEN, sin tilde."""
    assert texto_de_busqueda("almacén") == "ALMACEN"
    assert texto_de_busqueda("Jerónimo Martins") == "JERONIMO MARTINS"


def test_la_url_de_busqueda_agrupa_por_nit():
    """El directorio trae una fila por empresa y por anio: sin agrupar, D1
    salia cinco veces."""
    u = url_buscar_empresas("D1")
    assert "dd55-74ss" in u
    assert "%24group=nit" in u or "$group=nit" in u


def test_buscar_devuelve_un_nit_una_vez_aunque_el_portal_lo_repita():
    def traer(url):
        return [
            {"nit": "900276962", "razon_social": "D1 S.A.S.", "corte": "2025-12-31"},
            {"nit": "900276962", "razon_social": "D1 S.A.S.", "corte": "2024-12-31"},
            {"nit": "900480569", "razon_social": "JERONIMO MARTINS COLOMBIA S.A.S."},
        ]
    r = buscar_empresas("D1", traer)
    assert [e["nit"] for e in r] == ["900276962", "900480569"]
    assert r[0]["razon_social"] == "D1 S.A.S."


def test_buscar_con_menos_de_dos_letras_no_consulta_nada():
    """Dos letras si valen: "D1" es la empresa que mas se va a buscar."""
    llamadas = []
    assert buscar_empresas("d", lambda u: llamadas.append(u) or []) == []
    assert llamadas == []


# ------------------------------------------------------------------ cortes


def test_solo_cuentan_los_cortes_de_diciembre():
    """Supersociedades tambien publica cortes a 30 de junio, y un semestre no
    es un anio."""
    def traer(url):
        assert url == url_cortes("1")
        return [
            {"fecha_corte": "2023-12-31T00:00:00.000", "n": "60"},
            {"fecha_corte": "2024-06-30T00:00:00.000", "n": "96"},
            {"fecha_corte": "2024-12-31T00:00:00.000", "n": "92"},
            {"fecha_corte": "2025-12-31T00:00:00.000", "n": "58"},
        ]
    assert anios_con_balance("1", traer) == [2023, 2024, 2025]


# ------------------------------------------------------------- la descarga


def _fila(concepto, periodo, valor):
    return {"concepto": concepto, "periodo": periodo, "valor": str(valor)}


def _balance(actual, anterior):
    """Un balance minimo y cuadrado. `actual` y `anterior` escalan las cifras."""
    filas = []
    for p, k in (("Periodo Actual", actual), ("Periodo Anterior", anterior)):
        filas += [
            _fila("Efectivo y equivalentes al efectivo", p, 100 * k),
            _fila("Inventarios corrientes", p, 300 * k),
            _fila("Activos corrientes totales", p, 400 * k),
            _fila("Propiedades, planta y equipo", p, 600 * k),
            _fila("Total de activos", p, 1000 * k),
            _fila("Pasivos corrientes totales", p, 500 * k),
            _fila("Total de pasivos no corrientes", p, 200 * k),
            _fila("Total pasivos", p, 700 * k),
            _fila("Patrimonio total", p, 300 * k),
        ]
    return filas


def _resultados(actual, anterior):
    filas = []
    for p, k in (("Periodo Actual", actual), ("Periodo Anterior", anterior)):
        filas += [
            _fila("Ingresos de actividades ordinarias", p, 2000 * k),
            _fila("Costo de ventas", p, 1600 * k),
            _fila("Ganancia bruta", p, 400 * k),
            _fila("Gastos de administraci�n", p, 100 * k),
            _fila("Costos de distribuci�n", p, 200 * k),
            _fila("Ganancia (p�rdida) por actividades de operaci�n", p, 100 * k),
            _fila("Ganancia (p�rdida) procedente de operaciones continuadas", p, 60 * k),
        ]
    return filas


def _portal_de_mentira(llamadas=None):
    """Imita el portal: dos cortes, 2024 y 2025, cada uno con dos anios."""
    def traer(url):
        if llamadas is not None:
            llamadas.append(url)
        if "$group=fecha_corte" in url or "%24group=fecha_corte" in url:
            return [{"fecha_corte": f"{a}-12-31T00:00:00.000"} for a in (2022, 2023, 2024, 2025)]
        anio = 2025 if "2025-12-31" in url else 2024
        k = {2024: (2, 1), 2025: (3, 2)}[anio]     # actual, anterior
        if DATASET_BALANCE in url:
            return _balance(*k)
        if DATASET_RESULTADOS in url:
            return _resultados(*k)
        return []
    return traer


def test_dos_cortes_dan_tres_anios():
    ef = descargar_empresa("900276962", _portal_de_mentira(), "D1 S.A.S.")
    assert ef["periodos"] == ["2023", "2024", "2025"]
    assert ef["empresa"] == "D1 S.A.S."
    # el 2024 sale del corte de 2025 (k=2 en los dos: coinciden a proposito)
    assert ef["resultados"]["ventas"] == [2000, 4000, 6000]
    assert ef["balance"]["activo_total"] == [1000, 2000, 3000]


def test_solo_se_piden_los_dos_ultimos_cortes():
    llamadas = []
    descargar_empresa("1", _portal_de_mentira(llamadas))
    de_estados = [u for u in llamadas if "fecha_corte=" in u]
    assert len(de_estados) == 4, "dos datasets por dos cortes"
    assert all("2024-12-31" in u or "2025-12-31" in u for u in de_estados)
    assert not any("2023-12-31" in u for u in de_estados)


def test_los_costos_de_distribucion_se_suman_al_gasto_operacional():
    """D1 reporta un billon en "Costos de distribucion" y cero en "Gastos de
    ventas". Sin esta linea su utilidad operacional quedaba descuadrada en
    935 mil millones."""
    assert CONCEPTOS_SUMADOS["Costos de distribución"] == "gastos_operacionales"
    ef = descargar_empresa("1", _portal_de_mentira())
    # 100 + 200 por cada k
    assert ef["resultados"]["gastos_operacionales"] == [300, 600, 900]


def test_la_procedencia_viaja_con_los_estados():
    ef = descargar_empresa("900276962", _portal_de_mentira())
    p = ef["procedencia"]
    assert p["nit"] == "900276962"
    assert p["cortes"] == ["2024-12-31", "2025-12-31"]
    assert "Supersociedades" in p["fuente"] or "Superintendencia" in p["fuente"]
    assert p["descargado"]
    assert "fusion" not in ef, "el detalle de la union no debe salir al usuario"


def test_una_empresa_sin_cortes_avisa_y_menciona_la_superfinanciera():
    """Es el caso de Exito, Ecopetrol, Argos: cotizan en bolsa y le reportan a
    otra superintendencia."""
    with pytest.raises(ValueError) as e:
        descargar_empresa("890900608", lambda u: [])
    assert "Superfinanciera" in str(e.value)


def test_el_resultado_lo_entiende_el_motor():
    from motor.modelos import EstadosFinancieros
    from motor.indicadores import calcular_todos
    from motor.validacion import validar

    ef = EstadosFinancieros(descargar_empresa("1", _portal_de_mentira(), "Prueba"))
    ind = calcular_todos(ef)
    assert ind["margen_bruto"].valores[-1] == pytest.approx(20.0)
    assert not [h for h in validar(ef) if h.severidad == "error"]


# ------------------------------------------------------------------ el API


@pytest.fixture
def cliente():
    from fastapi.testclient import TestClient
    from api import app
    return TestClient(app)


def test_buscar_por_el_api_devuelve_nit_y_razon_social(cliente, monkeypatch):
    from herramientas import supersociedades
    monkeypatch.setattr(supersociedades, "traer_del_portal",
                        lambda u: [{"nit": "900276962", "razon_social": "D1 S.A.S."}])
    r = cliente.get("/api/supersociedades/buscar", params={"q": "d1"})
    assert r.status_code == 200
    assert r.json() == [{"nit": "900276962", "razon_social": "D1 S.A.S."}]


def test_sin_internet_el_api_avisa_con_503_y_no_se_cae(cliente, monkeypatch):
    """El dia de la exposicion no puede depender del wifi del salon: esto
    avisa y el resto de la aplicacion sigue andando."""
    from herramientas import supersociedades

    def sin_red(u):
        raise OSError("Name or service not known")
    monkeypatch.setattr(supersociedades, "traer_del_portal", sin_red)
    r = cliente.get("/api/supersociedades/buscar", params={"q": "d1"})
    assert r.status_code == 503
    assert "internet" in r.json()["detail"]
    # y lo que vive en disco sigue respondiendo
    assert cliente.get("/api/casos").status_code == 200


def test_cargar_por_nit_devuelve_el_formato_de_los_casos(cliente, monkeypatch):
    from herramientas import supersociedades
    monkeypatch.setattr(supersociedades, "traer_del_portal", _portal_de_mentira())
    r = cliente.post("/api/supersociedades/cargar",
                     json={"nit": "900276962", "razon_social": "D1 S.A.S."})
    assert r.status_code == 200, r.text
    ef = r.json()
    assert ef["periodos"] == ["2023", "2024", "2025"]
    assert ef["procedencia"]["nit"] == "900276962"
    # y ese mismo cuerpo lo acepta /api/analizar tal cual, con procedencia y todo
    assert cliente.post("/api/analizar", json=ef).status_code == 200


def test_la_procedencia_sobrevive_al_guardar_el_caso(cliente, monkeypatch, tmp_path):
    """Un caso guardado en disco no puede perder de donde salieron sus cifras."""
    import api
    from herramientas import supersociedades
    monkeypatch.setattr(supersociedades, "traer_del_portal", _portal_de_mentira())
    monkeypatch.setattr(api, "CASOS", tmp_path)
    ef = cliente.post("/api/supersociedades/cargar",
                      json={"nit": "900276962", "razon_social": "Prueba NIT"}).json()
    r = cliente.post("/api/casos", json={"estados": ef})
    assert r.status_code == 200, r.text
    import json
    guardado = json.loads((tmp_path / f"{r.json()['id']}.json").read_text(encoding="utf-8"))
    assert guardado["procedencia"]["nit"] == "900276962"


def test_un_nit_que_no_es_numero_no_llega_al_portal(cliente, monkeypatch):
    from herramientas import supersociedades
    llamadas = []
    monkeypatch.setattr(supersociedades, "traer_del_portal", lambda u: llamadas.append(u) or [])
    r = cliente.post("/api/supersociedades/cargar", json={"nit": "1' OR 1=1"})
    assert r.status_code == 422
    assert llamadas == []


def test_una_empresa_de_bolsa_da_422_con_explicacion(cliente, monkeypatch):
    from herramientas import supersociedades
    monkeypatch.setattr(supersociedades, "traer_del_portal", lambda u: [])
    r = cliente.post("/api/supersociedades/cargar", json={"nit": "890900608"})
    assert r.status_code == 422
    assert "Superfinanciera" in r.json()["detail"]
