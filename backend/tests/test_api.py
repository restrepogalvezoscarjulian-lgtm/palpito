"""Pruebas de la API HTTP."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api import app

CASO = Path(__file__).resolve().parents[2] / "casos" / "comercial_andina.json"


@pytest.fixture(scope="module")
def cliente():
    return TestClient(app)


@pytest.fixture(scope="module")
def datos():
    with open(CASO, encoding="utf-8") as fh:
        return json.load(fh)


def test_salud(cliente):
    r = cliente.get("/api/salud")
    assert r.status_code == 200
    assert r.json()["estado"] == "ok"


def test_lista_de_casos(cliente):
    casos = cliente.get("/api/casos").json()
    assert any(c["id"] == "comercial_andina" for c in casos)


def test_caso_inexistente_da_404(cliente):
    assert cliente.get("/api/casos/no_existe").status_code == 404


def test_analisis_de_caso_guardado(cliente):
    r = cliente.get("/api/casos/comercial_andina/analisis")
    assert r.status_code == 200
    assert r.json()["validacion"]["semaforo"] == "rojo"


def test_post_analizar_devuelve_estructura_completa(cliente, datos):
    r = cliente.post("/api/analizar", json=datos)
    assert r.status_code == 200
    cuerpo = r.json()
    for clave in ("validacion", "indicadores", "vertical", "horizontal",
                  "dupont", "puente_caja", "alertas", "recomendaciones"):
        assert clave in cuerpo, f"Falta '{clave}' en la respuesta"
    assert len(cuerpo["indicadores"]) >= 20
    assert len(cuerpo["alertas"]) > 0


def test_todo_indicador_serializa_su_trazabilidad(cliente, datos):
    """El modo docente del frontend depende de estos campos."""
    for i in cliente.post("/api/analizar", json=datos).json()["indicadores"]:
        assert i["formula"] and i["insumos"] and "disponible" in i


def test_periodos_inconsistentes_dan_422(cliente):
    malo = {"periodos": ["2023", "2024"], "balance": {"efectivo": [100]}}
    assert cliente.post("/api/analizar", json=malo).status_code == 422


def test_escenario_mejorar_cartera_vuelve_positivo_el_flujo(cliente, datos):
    """Simulacion: si la cartera baja, el flujo de caja libre deja de ser negativo."""
    base = cliente.post("/api/analizar", json=datos).json()
    assert base["puente_caja"]["flujo_caja_libre_aprox"] < 0

    mejorado = json.loads(json.dumps(datos))
    mejorado["balance"]["cuentas_por_cobrar"][1] = 1200
    nuevo = cliente.post("/api/analizar", json=mejorado).json()

    assert nuevo["puente_caja"]["flujo_caja_libre_aprox"] > 0
    assert len(nuevo["alertas"]) < len(base["alertas"])


def test_frontend_se_sirve(cliente):
    r = cliente.get("/")
    assert r.status_code == 200
    assert "Diagn" in r.text


def test_el_analisis_trae_el_puntaje_de_salud(cliente, datos):
    """El puntaje viaja con su metodología: sin ella el frontend no puede auditarlo."""
    s = cliente.post("/api/analizar", json=datos).json()["salud"]
    assert s["disponible"] is True
    assert 0 <= s["puntaje"] <= 100
    assert s["banda"]["nombre"] and s["metodologia"]["formula"]
    for d in s["dimensiones"]:
        for c in d["criterios"]:
            assert c["justificacion"] and c["fuente"] and len(c["escala"]) >= 2


def test_mejorar_la_cartera_sube_el_puntaje(cliente, datos):
    """Simulacion: si la cartera baja, el ciclo de caja se acorta y la nota sube.

    Es la prueba de que el puntaje reacciona al negocio y no es decorativo.
    """
    base = cliente.post("/api/analizar", json=datos).json()["salud"]["puntaje"]

    mejorado = json.loads(json.dumps(datos))
    mejorado["balance"]["cuentas_por_cobrar"][1] = 1200
    nuevo = cliente.post("/api/analizar", json=mejorado).json()["salud"]["puntaje"]

    assert nuevo > base


def test_la_ia_recibe_el_puntaje_ya_calculado(cliente):
    """El modelo no calcula la nota: la lee del contexto, igual que todo lo demas."""
    ctx = cliente.get("/api/contexto-ia").json()["contexto"]
    assert "PUNTAJE DE SALUD FINANCIERA" in ctx
    assert "70% x nivel" in ctx


# --------------------------------------------------------------- importacion


def _excel_demo():
    import io as _io

    from openpyxl import Workbook

    libro = Workbook()
    hoja = libro.active
    for fila in [
        ["Cuenta", "2023", "2024"],
        ["Efectivo y equivalentes", 450, 380],
        ["Deudores comerciales", 1800, 2400],
        ["Total activo corriente", 4350, 5680],
        ["Total pasivo corriente", 2100, 2800],
        ["Ingresos operacionales", 9800, 11200],
        ["Utilidad neta", 820, 700],
        ["Renglon rarisimo XYZ", 10, 20],
    ]:
        hoja.append(fila)
    buffer = _io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


def test_importar_excel_por_http(cliente):
    r = cliente.post("/api/importar",
                     files={"archivo": ("balance.xlsx", _excel_demo(),
                                        "application/vnd.ms-excel")})
    assert r.status_code == 200
    tabla = r.json()
    assert tabla["periodos"] == ["2023", "2024"]
    asignadas = {f["cuenta"] for f in tabla["filas"] if f["cuenta"]}
    assert "cuentas_por_cobrar" in asignadas and "ventas" in asignadas
    # La fila que nadie reconoce queda sin asignar y se avisa, no se adivina.
    rara = next(f for f in tabla["filas"] if "XYZ" in f["etiqueta"])
    assert rara["cuenta"] is None
    assert any("no se reconocieron" in a for a in tabla["avisos"])


def test_importar_formato_no_soportado_da_422(cliente):
    r = cliente.post("/api/importar",
                     files={"archivo": ("informe.docx", b"cualquier cosa", "text/plain")})
    assert r.status_code == 422
    assert "Formato no soportado" in r.json()["detail"]


def test_del_archivo_al_analisis_sin_digitar_nada(cliente):
    """El recorrido completo: subir, armar y analizar.

    Razón corriente 2024 = 5680 / 2800 = 2,0286 veces.
    """
    tabla = cliente.post("/api/importar",
                         files={"archivo": ("b.xlsx", _excel_demo(),
                                            "application/vnd.ms-excel")}).json()
    armado = cliente.post("/api/importar/armar",
                          json={**tabla, "empresa": "Importada S.A."})
    assert armado.status_code == 200
    datos = armado.json()
    assert datos["empresa"] == "Importada S.A."

    analisis = cliente.post("/api/analizar", json=datos).json()
    rc = next(i for i in analisis["indicadores"] if i["codigo"] == "razon_corriente")
    assert rc["valores"][1] == pytest.approx(5680 / 2800, abs=1e-4)


def test_armar_sin_ninguna_cuenta_asignada_da_422(cliente):
    r = cliente.post("/api/importar/armar",
                     json={"periodos": ["2024"],
                           "filas": [{"cuenta": None, "valores": [1]}]})
    assert r.status_code == 422


def test_catalogo_de_cuentas_para_la_interfaz(cliente):
    cuentas = cliente.get("/api/cuentas").json()
    codigos = {c["codigo"] for c in cuentas}
    assert {"efectivo", "ventas", "patrimonio"} <= codigos
    assert all(c["grupo"] in ("balance", "resultados") for c in cuentas)


# ------------------------------- lo que el motor ajusto tiene que verse


def test_los_ajustes_de_importacion_llegan_al_analisis(cliente):
    """El motor voltea signos y suma renglones de deuda. Antes lo anotaba en
    los supuestos y nadie leia ese campo: ni la interfaz, ni la validacion, ni
    el diagnostico. Decia "nunca en silencio" y lo hacia en silencio.
    """
    from motor.importacion import armar_estados

    estados = armar_estados({
        "periodos": ["2025"],
        "filas": [
            {"cuenta": "ventas", "valores": [1000]},
            {"cuenta": "costo_ventas", "valores": [-400]},
            {"cuenta": "deuda_financiera_lp", "valores": [100]},
            {"cuenta": "deuda_financiera_lp", "valores": [200]},
        ],
    }, empresa="Prueba")

    r = cliente.post("/api/analizar", json=estados)
    assert r.status_code == 200
    ajustes = r.json()["validacion"]["ajustes_importacion"]
    assert any("costo_ventas" in a for a in ajustes), ajustes
    assert any("deuda_financiera_lp" in a and "2 renglones" in a for a in ajustes), ajustes


def test_sin_ajustes_el_campo_viene_vacio_no_ausente(cliente, datos):
    """La interfaz decide si dibuja el bloque mirando la lista. Si el campo
    faltara tendria que adivinar.
    """
    r = cliente.post("/api/analizar", json=datos)
    assert r.status_code == 200
    assert r.json()["validacion"]["ajustes_importacion"] == []
