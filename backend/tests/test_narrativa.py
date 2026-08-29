"""Pruebas de la capa de narrativa.

No gastan creditos: la llamada a OpenRouter se simula. Lo que se verifica es
que el contexto que recibe el modelo este completo y que la aplicacion siga
funcionando cuando no hay clave configurada.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api
from motor import narrativa
from motor.modelos import EstadosFinancieros

CASO = Path(__file__).resolve().parents[2] / "casos" / "comercial_andina.json"


@pytest.fixture(scope="module")
def datos():
    with open(CASO, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def analisis(datos):
    return api._analizar(EstadosFinancieros(datos))


@pytest.fixture
def cliente():
    return TestClient(api.app)


@pytest.fixture
def sin_clave(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)


@pytest.fixture
def con_clave_falsa(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "clave-de-prueba")
    monkeypatch.setenv("OPENROUTER_MODELO", "deepseek/deepseek-v4-flash")


# ============================================ 1. DEGRADACION SIN CLAVE (clave)


def test_sin_clave_la_ia_se_reporta_no_disponible(sin_clave):
    assert narrativa.disponible() is False
    assert narrativa.estado()["disponible"] is False
    assert "clave" in narrativa.estado()["motivo"].lower()


def test_sin_clave_narrar_no_revienta(sin_clave, analisis):
    r = narrativa.narrar(analisis)
    assert r["disponible"] is False
    assert r["texto"] == ""


def test_sin_clave_el_analisis_numerico_sigue_completo(sin_clave, cliente, datos):
    """Lo esencial: la app NO depende de la IA para funcionar."""
    r = cliente.post("/api/analizar", json=datos).json()
    assert len(r["indicadores"]) >= 20
    assert len(r["alertas"]) > 0
    assert r["puente_caja"]["disponible"] is True


# ================================================ 2. EL CONTEXTO ESTA COMPLETO


def test_contexto_incluye_los_bloques_clave(analisis):
    ctx = narrativa.construir_contexto(analisis)
    for bloque in ("CALIDAD DE LOS DATOS", "INDICADORES CALCULADOS",
                   "VARIACION ENTRE PERIODOS", "DUPONT", "PUENTE DE CAJA",
                   "ALERTAS DETECTADAS"):
        assert bloque in ctx, f"Falta el bloque '{bloque}' en el contexto"


def test_contexto_lleva_las_cifras_criticas(analisis):
    ctx = narrativa.construir_contexto(analisis)
    for cifra in ("1,057", "670", "450", "-63", "770", "-140", "19.10", "77.27"):
        assert cifra in ctx, f"El contexto no incluye la cifra {cifra}"


def test_contexto_advierte_el_descuadre(analisis):
    ctx = narrativa.construir_contexto(analisis)
    assert "no cuadra" in ctx
    assert "ROJO" in ctx


def test_contexto_marca_los_datos_no_disponibles(analisis):
    """El modelo debe SABER que hay huecos, para no rellenarlos."""
    ctx = narrativa.construir_contexto(analisis)
    assert "no disponible" in ctx
    assert "depreciacion" in ctx


def test_instrucciones_prohiben_calcular():
    assert "NO calcules" in narrativa.INSTRUCCIONES
    assert "NO calcules" in narrativa.INSTRUCCIONES_PREGUNTA


def test_instrucciones_de_pregunta_exigen_citar_fuentes():
    assert "Fuentes:" in narrativa.INSTRUCCIONES_PREGUNTA


# ================================================== 3. LLAMADA SIMULADA AL LLM


def _simular_respuesta(monkeypatch, contenido="Diagnostico de prueba.", codigo=200):
    """Reemplaza httpx.post por una respuesta falsa. No gasta creditos."""
    capturado = {}

    class RespuestaFalsa:
        status_code = codigo
        text = "error simulado"

        def json(self):
            return {"choices": [{"message": {"content": contenido}}]}

    def post_falso(url, **kwargs):
        capturado["url"] = url
        capturado["json"] = kwargs.get("json")
        capturado["headers"] = kwargs.get("headers")
        return RespuestaFalsa()

    monkeypatch.setattr(narrativa.httpx, "post", post_falso)
    return capturado


def test_narrar_devuelve_el_texto_del_modelo(con_clave_falsa, monkeypatch, analisis):
    _simular_respuesta(monkeypatch, "La empresa vendio mas pero genero menos caja.")
    r = narrativa.narrar(analisis)
    assert r["disponible"] is True
    assert "menos caja" in r["texto"]
    assert r["modelo"] == "deepseek/deepseek-v4-flash"


def test_la_peticion_lleva_el_contexto_y_temperatura_baja(con_clave_falsa, monkeypatch, analisis):
    cap = _simular_respuesta(monkeypatch)
    narrativa.narrar(analisis)
    cuerpo = cap["json"]
    assert cuerpo["temperature"] <= 0.3, "La temperatura debe ser baja: queremos consistencia"
    assert cuerpo["model"] == "deepseek/deepseek-v4-flash"
    contenido_usuario = cuerpo["messages"][1]["content"]
    assert "PUENTE DE CAJA" in contenido_usuario
    assert "1,057" in contenido_usuario


def test_la_clave_viaja_en_el_encabezado_no_en_el_cuerpo(con_clave_falsa, monkeypatch, analisis):
    cap = _simular_respuesta(monkeypatch)
    narrativa.narrar(analisis)
    assert cap["headers"]["Authorization"] == "Bearer clave-de-prueba"
    assert "clave-de-prueba" not in json.dumps(cap["json"])


def test_error_de_openrouter_se_reporta_claro(con_clave_falsa, monkeypatch, analisis):
    _simular_respuesta(monkeypatch, codigo=401)
    with pytest.raises(RuntimeError, match="401"):
        narrativa.narrar(analisis)


def test_pregunta_vacia_se_rechaza(con_clave_falsa, monkeypatch, analisis):
    _simular_respuesta(monkeypatch)
    with pytest.raises(ValueError, match="vacia"):
        narrativa.responder(analisis, "   ")


def test_pregunta_muy_larga_se_rechaza(con_clave_falsa, monkeypatch, analisis):
    _simular_respuesta(monkeypatch)
    with pytest.raises(ValueError, match="larga"):
        narrativa.responder(analisis, "a" * 501)


def test_responder_incluye_la_pregunta_en_el_mensaje(con_clave_falsa, monkeypatch, analisis):
    cap = _simular_respuesta(monkeypatch, "Respuesta.\nFuentes: Ventas 8,900 -> 10,600")
    r = narrativa.responder(analisis, "Por que tengo menos plata si vendi mas?")
    assert "menos plata" in cap["json"]["messages"][1]["content"]
    assert "Fuentes:" in r["texto"]


# ======================================================= 4. ENDPOINTS DE LA API


def test_endpoint_salud_reporta_estado_de_la_ia(cliente):
    assert "ia" in cliente.get("/api/salud").json()


def test_endpoint_contexto_ia_es_auditable(cliente):
    """Transparencia: cualquiera puede ver que se le manda al modelo."""
    r = cliente.get("/api/contexto-ia?caso_id=comercial_andina")
    assert r.status_code == 200
    assert "PUENTE DE CAJA" in r.json()["contexto"]


def test_endpoint_narrar_sin_clave_responde_no_disponible(sin_clave, cliente, datos):
    r = cliente.post("/api/narrar", json={"estados": datos})
    assert r.status_code == 200
    assert r.json()["disponible"] is False


def test_endpoint_preguntar_con_clave_simulada(con_clave_falsa, monkeypatch, cliente, datos):
    _simular_respuesta(monkeypatch, "Porque la cartera crecio.\nFuentes: cartera +34.40%")
    r = cliente.post("/api/preguntar",
                     json={"estados": datos, "pregunta": "Por que tengo menos plata?"})
    assert r.status_code == 200
    assert "cartera" in r.json()["texto"]
