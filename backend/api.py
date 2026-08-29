"""API HTTP del diagnostico financiero.

Expone el motor por HTTP y sirve la interfaz web. Un solo servicio, un solo
contenedor. La clave de OpenRouter (bloque 3) vivira aqui, del lado del
servidor, nunca en el navegador.

Correr en local:  uvicorn api:app --reload
Documentacion:    http://localhost:8000/docs
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from motor.diagnostico import diagnosticar, recomendaciones
from motor.indicadores import (
    analisis_horizontal,
    analisis_vertical,
    calcular_todos,
    dupont,
    puente_caja,
)
from motor import narrativa
from motor.modelos import EstadosFinancieros
from motor.validacion import resumen, semaforo, validar

RAIZ = Path(__file__).resolve().parents[1]
CASOS = RAIZ / "casos"
FRONTEND = RAIZ / "frontend"

# Carga el archivo .env si existe (sin dependencias externas)
_ENV = Path(__file__).resolve().parents[1] / ".env"
if _ENV.exists():
    import os
    for _linea in _ENV.read_text(encoding="utf-8").splitlines():
        _linea = _linea.strip()
        if _linea and not _linea.startswith("#") and "=" in _linea:
            _k, _v = _linea.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

app = FastAPI(
    title="Palpito",
    description=(
        "Motor deterministico de analisis financiero. Los indicadores se calculan "
        "con formulas auditables; la inteligencia artificial solo redacta sobre "
        "resultados ya verificados."
    ),
    version="0.3.0",
)


# ------------------------------------------------------------------ esquemas


class EntradaNarrativa(BaseModel):
    """Estados financieros + (opcionalmente) una pregunta libre."""
    estados: "EntradaEstados"
    pregunta: str | None = None


class EntradaEstados(BaseModel):
    empresa: str = "Sin nombre"
    moneda: str = "COP"
    unidad: str = "millones"
    periodos: list[str]
    balance: dict[str, list[float | None]] = Field(default_factory=dict)
    resultados: dict[str, list[float | None]] = Field(default_factory=dict)
    supuestos: dict = Field(default_factory=dict)


# --------------------------------------------------------------- utilidades


def _analizar(ef: EstadosFinancieros) -> dict:
    """Ejecuta la cadena completa: validar -> calcular -> diagnosticar."""
    hallazgos = validar(ef)
    indicadores = calcular_todos(ef)
    alertas = diagnosticar(ef)

    return {
        "empresa": ef.empresa,
        "moneda": ef.moneda,
        "unidad": ef.unidad,
        "periodos": ef.periodos,
        "validacion": {
            "semaforo": semaforo(hallazgos),
            "resumen": resumen(hallazgos),
            "hallazgos": [asdict(h) for h in hallazgos],
        },
        "indicadores": [
            {**asdict(i), "disponible": i.disponible, "variacion": i.variacion()}
            for i in indicadores.values()
        ],
        "vertical": analisis_vertical(ef),
        "horizontal": analisis_horizontal(ef),
        "dupont": dupont(ef),
        "puente_caja": puente_caja(ef),
        "alertas": [asdict(a) for a in alertas],
        "recomendaciones": recomendaciones(alertas),
    }


# ---------------------------------------------------------------- endpoints


@app.get("/api/salud", tags=["sistema"])
def salud():
    return {"estado": "ok", "version": app.version, "ia": narrativa.estado()}


@app.get("/api/casos", tags=["casos"])
def listar_casos():
    """Casos de ejemplo incluidos en el repositorio."""
    salida = []
    for ruta in sorted(CASOS.glob("*.json")):
        with open(ruta, encoding="utf-8") as fh:
            datos = json.load(fh)
        salida.append(
            {
                "id": ruta.stem,
                "empresa": datos.get("empresa", ruta.stem),
                "periodos": datos.get("periodos", []),
            }
        )
    return salida


@app.get("/api/casos/{caso_id}", tags=["casos"])
def obtener_caso(caso_id: str):
    """Devuelve los datos crudos de un caso, para poder editarlos."""
    ruta = CASOS / f"{caso_id}.json"
    if not ruta.exists() or ruta.parent != CASOS:
        raise HTTPException(404, f"No existe el caso '{caso_id}'.")
    with open(ruta, encoding="utf-8") as fh:
        return json.load(fh)


@app.get("/api/casos/{caso_id}/analisis", tags=["analisis"])
def analizar_caso(caso_id: str):
    """Analisis completo de un caso guardado."""
    ruta = CASOS / f"{caso_id}.json"
    if not ruta.exists() or ruta.parent != CASOS:
        raise HTTPException(404, f"No existe el caso '{caso_id}'.")
    return _analizar(EstadosFinancieros.desde_json(ruta))


@app.post("/api/analizar", tags=["analisis"])
def analizar(entrada: EntradaEstados):
    """Analiza estados financieros enviados por el usuario."""
    try:
        ef = EstadosFinancieros(entrada.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _analizar(ef)


@app.post("/api/narrar", tags=["ia"])
def narrar(entrada: EntradaNarrativa):
    """Redacta el diagnostico en prosa.

    La IA solo recibe numeros ya calculados por el motor; no hace aritmetica.
    """
    try:
        ef = EstadosFinancieros(entrada.estados.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    try:
        return narrativa.narrar(_analizar(ef))
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from exc


@app.post("/api/preguntar", tags=["ia"])
def preguntar(entrada: EntradaNarrativa):
    """Responde una pregunta libre anclada a los datos de la empresa."""
    try:
        ef = EstadosFinancieros(entrada.estados.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    try:
        return narrativa.responder(_analizar(ef), entrada.pregunta or "")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from exc


@app.get("/api/contexto-ia", tags=["ia"])
def contexto_ia(caso_id: str = "comercial_andina"):
    """Muestra EXACTAMENTE el texto que se le envia al modelo.

    Existe por transparencia: permite auditar que la IA no recibe nada que el
    motor no haya calculado antes.
    """
    ruta = CASOS / f"{caso_id}.json"
    if not ruta.exists() or ruta.parent != CASOS:
        raise HTTPException(404, f"No existe el caso '{caso_id}'.")
    analisis = _analizar(EstadosFinancieros.desde_json(ruta))
    return {"contexto": narrativa.construir_contexto(analisis)}


# ------------------------------------------------------------------ interfaz

if FRONTEND.exists():
    @app.get("/", include_in_schema=False)
    def inicio():
        return FileResponse(FRONTEND / "index.html")

    app.mount("/", StaticFiles(directory=FRONTEND), name="frontend")
