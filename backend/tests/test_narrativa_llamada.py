"""Pruebas de la llamada al modelo, sin salir a internet.

Salieron de una falla real del 10-sep-2026: la cabecera HTTP `X-Title` decia
"Palpito - Diagnostico Financiero" CON tilde, y una cabecera HTTP solo admite
ASCII. La llamada reventaba antes de salir del computador, con
"'ascii' codec can't encode character '\xf3' in position 15".

Encima, las tres rutas de IA atrapaban solo RuntimeError. Como
UnicodeEncodeError hereda de ValueError y no de RuntimeError, la excepcion se
escapaba, FastAPI devolvia "Internal Server Error" en texto plano, y la interfaz
-que esperaba JSON- mostraba "Unexpected token 'I'". Tres errores apilados y
ninguno decia que habia pasado.
"""

import json

import pytest
from fastapi.testclient import TestClient

from api import app
from motor import narrativa


@pytest.fixture
def cliente():
    return TestClient(app)


ESTADOS = {
    "empresa": "Prueba",
    "periodos": ["2023", "2024"],
    "balance": {
        "activo_corriente": [2950, 3620], "pasivo_corriente": [1650, 2050],
        "activo_total": [7100, 8300], "patrimonio": [3600, 3900],
        "inventarios": [1100, 1500], "efectivo": [680, 290],
    },
    "resultados": {
        "ventas": [8200, 9766], "costo_ventas": [5330, 6640],
        "utilidad_neta": [420, 359], "utilidad_bruta": [2870, 3126],
    },
}


# ------------------------------------------------ la cabecera que reventaba


def test_las_cabeceras_de_la_llamada_son_todas_ascii(monkeypatch):
    """Una cabecera HTTP no admite tildes. Ni una.

    Es el unico texto del proyecto donde la tilde esta PROHIBIDA: este no lo lee
    una persona, lo lee un servidor.
    """
    capturadas = {}

    class RespuestaFalsa:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {"choices": [{"message": {"content": "ok"}}]}

    def post_falso(url, **kwargs):
        capturadas.update(kwargs.get("headers") or {})
        return RespuestaFalsa()

    monkeypatch.setattr(narrativa, "api_key", lambda: "clave-de-prueba")
    monkeypatch.setattr(narrativa.httpx, "post", post_falso)

    narrativa._llamar([{"role": "user", "content": "hola"}])

    assert capturadas, "no se capturo ninguna cabecera"
    for nombre, valor in capturadas.items():
        assert str(nombre).isascii(), f"el nombre de cabecera {nombre!r} no es ASCII"
        assert str(valor).isascii(), (
            f"la cabecera {nombre} lleva un caracter que rompe la llamada: {valor!r}")


def test_la_clave_no_viaja_en_el_titulo(monkeypatch):
    """La clave solo va en Authorization, nunca en otra cabecera."""
    capturadas = {}

    class RespuestaFalsa:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr(narrativa, "api_key", lambda: "SECRETO-123")
    monkeypatch.setattr(narrativa.httpx, "post",
                        lambda url, **kw: (capturadas.update(kw.get("headers") or {}),
                                           RespuestaFalsa())[1])
    narrativa._llamar([{"role": "user", "content": "hola"}])

    for nombre, valor in capturadas.items():
        if nombre.lower() != "authorization":
            assert "SECRETO-123" not in str(valor), nombre


# --------------------------- un fallo del modelo no puede tumbar la respuesta


@pytest.mark.parametrize("explosion", [
    UnicodeEncodeError("ascii", "Diagnóstico", 5, 6, "ordinal not in range(128)"),
    RuntimeError("OpenRouter respondio 429"),
    ValueError("algo raro"),
    KeyError("choices"),
])
def test_cualquier_fallo_de_ia_sale_como_json_y_no_como_500(cliente, monkeypatch,
                                                            explosion):
    """Lo que la IA no pueda redactar no invalida los numeros, que ya estan
    calculados sin ella. Pero el mensaje tiene que poder leerse.
    """
    def revienta(*_a, **_k):
        raise explosion

    monkeypatch.setattr(narrativa, "narrar", revienta)

    r = cliente.post("/api/narrar", json={"estados": ESTADOS})
    assert r.status_code == 502, r.status_code
    cuerpo = r.json()                       # tiene que ser JSON, no texto plano
    assert "IA" in cuerpo["detail"]
    assert "siguen siendo válidos" in cuerpo["detail"]


def test_una_falla_del_servidor_no_se_reporta_como_culpa_del_usuario(cliente,
                                                                    monkeypatch):
    """UnicodeEncodeError hereda de ValueError, asi que /api/preguntar lo
    reportaba como 422 -pregunta invalida- cuando el problema era del servidor.
    """
    def revienta(*_a, **_k):
        raise UnicodeEncodeError("ascii", "ó", 0, 1, "ordinal not in range(128)")

    monkeypatch.setattr(narrativa, "responder", revienta)

    r = cliente.post("/api/preguntar",
                     json={"estados": ESTADOS, "pregunta": "¿como voy?"})
    assert r.status_code == 502, f"reporto {r.status_code}, que culpa al usuario"
    assert "IA" in r.json()["detail"]


def test_una_pregunta_vacia_si_es_culpa_del_usuario(cliente, monkeypatch):
    """La otra mitad: un 422 de verdad tiene que seguir siendo 422."""
    def rechaza(*_a, **_k):
        raise ValueError("La pregunta viene vacia.")

    monkeypatch.setattr(narrativa, "responder", rechaza)

    r = cliente.post("/api/preguntar", json={"estados": ESTADOS, "pregunta": ""})
    assert r.status_code == 422


# ------------------------------------------------- la respuesta que llega vacia
#
# Pasó el 11-sep con D1: el modelo se puso a "pensar" antes de responder, se
# gastó los 700 tokens del límite en el razonamiento y la respuesta llegó con
# content: null. La pantalla decía "'NoneType' object has no attribute 'strip'".


def _post_que_devuelve(cuerpo, capturado=None):
    class RespuestaFalsa:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return cuerpo

    def post_falso(url, **kwargs):
        if capturado is not None:
            capturado.update(kwargs.get("json") or {})
        return RespuestaFalsa()
    return post_falso


def test_la_llamada_apaga_el_razonamiento_interno(monkeypatch):
    """Aquí no hay nada que razonar: recibe números resueltos y los redacta."""
    enviado = {}
    monkeypatch.setattr(narrativa, "api_key", lambda: "clave-de-prueba")
    monkeypatch.setattr(narrativa.httpx, "post",
                        _post_que_devuelve({"choices": [{"message": {"content": "ok"}}]}, enviado))
    narrativa._llamar([{"role": "user", "content": "hola"}])
    assert enviado["reasoning"] == {"enabled": False}


def test_una_respuesta_vacia_por_falta_de_espacio_se_explica(monkeypatch):
    monkeypatch.setattr(narrativa, "api_key", lambda: "clave-de-prueba")
    monkeypatch.setattr(narrativa.httpx, "post", _post_que_devuelve({
        "choices": [{"finish_reason": "length",
                     "message": {"content": None, "reasoning": "pensando..."}}]}))
    with pytest.raises(RuntimeError) as e:
        narrativa._llamar([{"role": "user", "content": "hola"}])
    assert "NoneType" not in str(e.value)
    assert "agotó" in str(e.value)


def test_una_respuesta_vacia_sin_motivo_tambien_avisa_en_castellano(monkeypatch):
    monkeypatch.setattr(narrativa, "api_key", lambda: "clave-de-prueba")
    monkeypatch.setattr(narrativa.httpx, "post", _post_que_devuelve({
        "choices": [{"finish_reason": "stop", "message": {"content": "   "}}]}))
    with pytest.raises(RuntimeError) as e:
        narrativa._llamar([{"role": "user", "content": "hola"}])
    assert "vacía" in str(e.value)
