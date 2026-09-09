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

from fastapi import FastAPI, File, HTTPException, UploadFile
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
from motor.importacion import CUENTAS, GRUPO, armar_estados, importar
from motor.salud import puntaje_salud
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
        "salud": puntaje_salud(ef),
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


# -------------------------------------------------------------- importacion

MAX_ARCHIVO = 8 * 1024 * 1024   # 8 MB: un estado financiero no pesa mas


class EntradaEtiquetas(BaseModel):
    etiquetas: list[str] = Field(default_factory=list, max_length=60)


class EntradaTabla(BaseModel):
    periodos: list[str]
    filas: list[dict] = Field(default_factory=list)
    empresa: str = ""
    moneda: str = "COP"
    unidad: str = "millones"


@app.post("/api/importar", tags=["importacion"])
async def importar_archivo(archivo: UploadFile = File(...)):
    """Lee un Excel, CSV o PDF y devuelve la tabla con un mapeo propuesto.

    No calcula ni valida nada financiero: solo lee. El usuario confirma el
    mapeo en pantalla y solo entonces se arman los estados financieros.
    """
    contenido = await archivo.read()
    if len(contenido) > MAX_ARCHIVO:
        raise HTTPException(413, f"El archivo pesa mas de {MAX_ARCHIVO // (1024 * 1024)} MB.")
    try:
        tabla = importar(archivo.filename or "", contenido)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:  # archivo corrupto, protegido, formato raro
        raise HTTPException(
            422, f"No se pudo leer el archivo: {exc}. Si es un PDF escaneado o un "
                 "Excel protegido, exporte los datos a CSV e intente de nuevo.") from exc
    return tabla.como_dict()


@app.get("/api/cuentas", tags=["importacion"])
def cuentas_disponibles():
    """Catalogo de cuentas que entiende el motor, para las listas de la interfaz."""
    return [{"codigo": c, "grupo": GRUPO[c]} for c in CUENTAS]


@app.post("/api/importar/proponer", tags=["importacion"])
def proponer_mapeo(entrada: EntradaEtiquetas):
    """Le pide al modelo una propuesta para las filas que el diccionario no reconocio.

    Es clasificacion de texto, no calculo: el modelo mira COMO SE LLAMA la fila,
    nunca cuanto vale. La propuesta llega marcada y no se aplica sola.
    """
    try:
        return narrativa.proponer_cuentas(entrada.etiquetas, CUENTAS)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.post("/api/importar/armar", tags=["importacion"])
def armar_desde_tabla(entrada: EntradaTabla):
    """Convierte la tabla ya confirmada por el usuario en estados financieros.

    Devuelve el mismo formato de los casos de la carpeta casos/, listo para
    editarse o analizarse con los endpoints que ya existen.
    """
    try:
        return armar_estados(entrada.model_dump(), empresa=entrada.empresa,
                             moneda=entrada.moneda, unidad=entrada.unidad)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


# ------------------------------------------------------------------ interfaz

if FRONTEND.exists():
    @app.get("/", include_in_schema=False)
    def inicio():
        return FileResponse(FRONTEND / "index.html")

    app.mount("/", StaticFiles(directory=FRONTEND), name="frontend")
