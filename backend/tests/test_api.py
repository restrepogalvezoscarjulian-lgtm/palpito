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


# --------------------------------- guardar una empresa cargada (opcion A)


ESTADOS_NUEVOS = {
    "empresa": "Cementos de Prueba S.A.", "moneda": "COP", "unidad": "millones",
    "periodos": ["2023", "2024"],
    "balance": {"efectivo": [100, 200], "activo_total": [1000, 1100],
                "patrimonio": [400, 450], "pasivo_corriente": [300, 320],
                "activo_corriente": [500, 560]},
    "resultados": {"ventas": [5000, 5500], "costo_ventas": [3000, 3200],
                   "utilidad_neta": [300, 350]},
}


@pytest.fixture
def limpiar_guardados(tmp_path, monkeypatch):
    """Manda las escrituras a una carpeta temporal, NO a casos/.

    La primera version de estas pruebas escribia en la carpeta de verdad, y una
    prueba que fallo a mitad dejo ahi un archivo suelto. Los tres casos del
    taller son la evidencia de auditoria del proyecto: una prueba no puede
    tener permiso de tocar esa carpeta, ni por accidente.
    """
    import shutil

    import api

    for nombre in ("comercial_andina", "andina_trienio", "andina_con_benchmark"):
        origen = api.CASOS / f"{nombre}.json"
        if origen.exists():
            shutil.copy(origen, tmp_path / f"{nombre}.json")
    monkeypatch.setattr(api, "CASOS", tmp_path)
    yield []


def test_una_empresa_cargada_se_puede_guardar(cliente, limpiar_guardados):
    r = cliente.post("/api/casos", json={"estados": ESTADOS_NUEVOS})
    assert r.status_code == 200, r.text
    guardado = r.json()
    assert guardado["id"] == "cementos_de_prueba_s_a"
    assert guardado["sobrescrito"] is False
    # y desde ese momento aparece en la lista y se puede volver a abrir
    assert any(c["id"] == guardado["id"] for c in cliente.get("/api/casos").json())
    assert cliente.get(f"/api/casos/{guardado['id']}").json()["periodos"] == ["2023", "2024"]


@pytest.mark.parametrize("empresa", [
    "Comercial Andina",          # -> comercial_andina
    "comercial andina",
    "COMERCIAL  ANDINA",
    "Comercial-Andina",
    "Andina Trienio",            # -> andina_trienio
    "andina con benchmark",      # -> andina_con_benchmark
])
def test_los_casos_del_taller_no_se_pueden_pisar(cliente, empresa,
                                                limpiar_guardados):
    """Son la evidencia de auditoria del proyecto: la suite los verifica contra
    valores calculados a mano. Ningun nombre que caiga en su archivo puede
    sobrescribirlos, ni siquiera pidiendolo explicitamente.
    """
    r = cliente.post("/api/casos",
                     json={"estados": dict(ESTADOS_NUEVOS, empresa=empresa),
                           "sobrescribir": True})
    assert r.status_code == 409, f"'{empresa}' pudo pisar un caso del taller"
    assert "taller" in r.json()["detail"]


def test_los_tres_casos_del_taller_siguen_intactos(cliente):
    """La red debajo de la red: despues de todas las pruebas de guardado, los
    tres archivos tienen que seguir dando lo mismo.
    """
    esperado = {"comercial_andina": ["2023", "2024"],
                "andina_trienio": ["2022", "2023", "2024"],
                "andina_con_benchmark": ["2022", "2023", "2024"]}
    for caso, periodos in esperado.items():
        assert cliente.get(f"/api/casos/{caso}").json()["periodos"] == periodos


def test_un_nombre_parecido_pero_distinto_si_se_guarda(cliente, limpiar_guardados):
    """La proteccion no puede ser tan ancha que estorbe: "Comercial Andina
    S.A." cae en otro archivo y es legitimo guardarla.
    """
    r = cliente.post("/api/casos",
                     json={"estados": dict(ESTADOS_NUEVOS,
                                           empresa="Comercial Andina S.A.")})
    assert r.status_code == 200, r.text
    assert r.json()["id"] == "comercial_andina_s_a"


def test_guardar_dos_veces_pide_confirmacion(cliente, limpiar_guardados):
    r = cliente.post("/api/casos", json={"estados": ESTADOS_NUEVOS})
    repetido = cliente.post("/api/casos", json={"estados": ESTADOS_NUEVOS})
    assert repetido.status_code == 409
    assert "Ya existe" in repetido.json()["detail"]
    forzado = cliente.post("/api/casos",
                           json={"estados": ESTADOS_NUEVOS, "sobrescribir": True})
    assert forzado.status_code == 200
    assert forzado.json()["sobrescrito"] is True


@pytest.mark.parametrize("empresa", [
    "../../fuera", r"..\..\fuera", "carpeta/otra", "C:/Windows/system32",
])
def test_un_nombre_con_ruta_no_escribe_fuera_de_casos(cliente, empresa,
                                                      limpiar_guardados):
    """El nombre viaja desde el navegador: no puede terminar escribiendo en
    otra carpeta.
    """
    from api import CASOS
    r = cliente.post("/api/casos",
                     json={"estados": dict(ESTADOS_NUEVOS, empresa=empresa)})
    assert r.status_code == 200, r.text
    guardado = r.json()
    ruta = (CASOS / f"{guardado['id']}.json").resolve()
    assert ruta.parent == CASOS.resolve(), f"escribio en {ruta}"
    assert ".." not in guardado["id"] and "/" not in guardado["id"]


def test_sin_periodos_no_se_guarda(cliente, limpiar_guardados):
    r = cliente.post("/api/casos",
                     json={"estados": dict(ESTADOS_NUEVOS, periodos=[])})
    assert r.status_code == 422


# ----------------------------------------- borrar un caso guardado (punto 2)


def test_un_caso_guardado_se_puede_borrar(cliente, limpiar_guardados):
    creado = cliente.post("/api/casos", json={"estados": ESTADOS_NUEVOS}).json()
    assert cliente.get(f"/api/casos/{creado['id']}").status_code == 200
    r = cliente.delete(f"/api/casos/{creado['id']}")
    assert r.status_code == 200, r.text
    assert cliente.get(f"/api/casos/{creado['id']}").status_code == 404


@pytest.mark.parametrize("caso", [
    "comercial_andina", "andina_trienio", "andina_con_benchmark",
])
def test_los_casos_del_taller_no_se_pueden_borrar(cliente, caso, limpiar_guardados):
    r = cliente.delete(f"/api/casos/{caso}")
    assert r.status_code == 403, f"{caso} se pudo borrar"
    assert "taller" in r.json()["detail"]
    # y siguen ahi
    assert cliente.get(f"/api/casos/{caso}").status_code == 200


def test_borrar_algo_que_no_existe_lo_dice(cliente, limpiar_guardados):
    assert cliente.delete("/api/casos/no_existe_nada").status_code == 404


@pytest.mark.parametrize("id_malo", ["../../otro", r"..\..\otro", "sub/carpeta",
                                    "..", ".", "casos"])
def test_borrar_no_puede_salirse_de_la_carpeta(cliente, id_malo, limpiar_guardados,
                                               tmp_path):
    """Lo que importa no es QUE codigo devuelve, sino que no borre nada."""
    import api

    testigo = api.CASOS / "testigo.json"
    testigo.write_text("{}", encoding="utf-8")
    r = cliente.delete(f"/api/casos/{id_malo}")
    assert r.status_code >= 400, f"{id_malo} devolvio {r.status_code}"
    assert testigo.exists(), f"{id_malo} borro algo que no debia"
    assert list(api.CASOS.iterdir()), "se vacio la carpeta"


# ------------------------------------------------ sectores ya calculados
#
# La aplicacion LEE las referencias del disco y nunca consulta internet, ni al
# abrir la pantalla ni el dia de una exposicion. Reconstruir un sector es un
# acto deliberado que se corre aparte con herramientas/construir_benchmark.


def test_la_lista_de_sectores_trae_su_procedencia(cliente):
    r = cliente.get("/api/sectores")
    assert r.status_code == 200
    lista = r.json()
    assert isinstance(lista, list)
    if not lista:
        return                      # todavia no se ha construido ningun sector
    s = lista[0]
    for campo in ("ciiu", "nombre", "anio", "empresas", "indicadores"):
        assert campo in s, campo


def test_un_sector_devuelve_medianas_y_cuartiles(cliente):
    lista = cliente.get("/api/sectores").json()
    if not lista:
        return
    ciiu = lista[0]["ciiu"]
    d = cliente.get(f"/api/sectores/{ciiu}").json()
    assert d["benchmark"], "sin medianas"
    assert d["cuartiles"], "sin cuartiles"
    assert "Superintendencia" in d["fuente"]
    assert d["anio"] and d["empresas_usadas"]
    un_codigo = next(iter(d["benchmark"]))
    q = d["cuartiles"][un_codigo]
    assert q["p25"] <= q["mediana"] <= q["p75"], q


def test_un_sector_que_no_existe_responde_404(cliente):
    assert cliente.get("/api/sectores/0000").status_code == 404


def test_el_ciiu_no_puede_salirse_de_la_carpeta_de_referencias(cliente):
    """Un CIIU es un numero: todo lo demas se descarta antes de abrir nada."""
    for intento in ("../../.env", "..%2F..%2F.env", "....//....//.env"):
        r = cliente.get(f"/api/sectores/{intento}")
        assert r.status_code in (404, 400), (intento, r.status_code)


def test_las_referencias_del_sector_sirven_para_comparar(cliente, datos):
    """De punta a punta: lo que da /api/sectores entra en /api/benchmark."""
    lista = cliente.get("/api/sectores").json()
    if not lista:
        return
    refs = cliente.get(f"/api/sectores/{lista[0]['ciiu']}").json()["benchmark"]
    r = cliente.post("/api/benchmark", json={"estados": datos, "referencias": refs})
    assert r.status_code == 200
    comparadas = [c for c in r.json()["comparaciones"]
                  if c["veredicto"] != "sin_referencia"]
    assert comparadas, "no comparo ningun indicador contra el sector"
