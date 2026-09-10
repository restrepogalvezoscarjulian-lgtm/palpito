"""API HTTP del diagnóstico financiero.

Expone el motor por HTTP y sirve la interfaz web. Un solo servicio, un solo
contenedor. La clave de OpenRouter (bloque 3) vivira aquí, del lado del
servidor, nunca en el navegador.

Correr en local:  uvicorn api:app --reload
Documentacion:    http://localhost:8000/docs
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
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
from motor.benchmark import codigos_comparables, comparar
from motor.importacion import CUENTAS, GRUPO, armar_estados, importar
from motor.proyectos import (
    Proyecto,
    calcular_wacc,
    evaluar_proyecto,
    flujo_caja_mensual,
)
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
        "Motor determinista de análisis financiero. Los indicadores se calculan "
        "con fórmulas auditables; la inteligencia artificial solo redacta sobre "
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
            # Lo que el motor tuvo que cambiar para poder leer el archivo:
            # voltear un signo, sumar dos renglones de deuda. Va aqui, junto a
            # la calidad de los datos, porque hasta ahora se anotaba en los
            # supuestos y NADIE lo leia: ni la interfaz, ni la validacion, ni
            # el diagnostico. El motor decia "nunca en silencio" y lo hacia en
            # silencio. Quien mira una cifra tiene derecho a saber que no vino
            # tal cual del PDF.
            "ajustes_importacion": list(ef.supuestos.get("ajustes_importacion") or []),
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
        "benchmark": comparar(indicadores, ef.supuestos.get("benchmark")),
        "comparables": codigos_comparables(indicadores),
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
    """Análisis completo de un caso guardado."""
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


def _falla_de_ia(exc: Exception) -> str:
    """Convierte cualquier tropiezo del modelo en un mensaje que se pueda leer.

    Las tres rutas de IA atrapaban solo RuntimeError. Cuando la llamada fallo
    por otra cosa -una tilde en una cabecera HTTP, que lanza UnicodeEncodeError-
    la excepcion se escapo, FastAPI devolvio "Internal Server Error" en texto
    plano, y la interfaz, que esperaba JSON, mostro "Unexpected token 'I'".
    Dos errores encima del verdadero, y ninguno decia que habia pasado.

    Lo que la IA no pueda redactar no invalida nada: los numeros ya estan
    calculados sin ella.
    """
    detalle = str(exc).strip() or exc.__class__.__name__
    return (f"La redacción con IA falló: {detalle}. "
            f"Los indicadores, las alertas y el puntaje de esta página se "
            f"calcularon sin IA y siguen siendo válidos.")


@app.post("/api/narrar", tags=["ia"])
def narrar(entrada: EntradaNarrativa):
    """Redacta el diagnóstico en prosa.

    La IA solo recibe números ya calculados por el motor; no hace aritmetica.
    """
    try:
        ef = EstadosFinancieros(entrada.estados.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    try:
        return narrativa.narrar(_analizar(ef))
    except Exception as exc:                     # noqa: BLE001
        raise HTTPException(502, _falla_de_ia(exc)) from exc


@app.post("/api/preguntar", tags=["ia"])
def preguntar(entrada: EntradaNarrativa):
    """Responde una pregunta libre anclada a los datos de la empresa."""
    try:
        ef = EstadosFinancieros(entrada.estados.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    try:
        return narrativa.responder(_analizar(ef), entrada.pregunta or "")
    except UnicodeError as exc:
        # UnicodeEncodeError hereda de ValueError, asi que sin esta rama se
        # reportaba como "pregunta invalida" (422) una falla que era del
        # servidor, no del usuario.
        raise HTTPException(502, _falla_de_ia(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:                     # noqa: BLE001
        raise HTTPException(502, _falla_de_ia(exc)) from exc


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
async def importar_archivo(archivo: UploadFile = File(...), paginas: str = Form("")):
    """Lee un Excel, CSV o PDF y devuelve la tabla con un mapeo propuesto.

    No calcula ni valida nada financiero: solo lee. El usuario confirma el
    mapeo en pantalla y solo entonces se arman los estados financieros.
    """
    contenido = await archivo.read()
    if len(contenido) > MAX_ARCHIVO:
        raise HTTPException(413, f"El archivo pesa más de {MAX_ARCHIVO // (1024 * 1024)} MB.")
    try:
        tabla = importar(archivo.filename or "", contenido, paginas)
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

    Es clasificación de texto, no cálculo: el modelo mira COMO SE LLAMA la fila,
    nunca cuánto vale. La propuesta llega marcada y no se aplica sola.
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


# --------------------------------------------------------------- benchmark


class EntradaBenchmark(BaseModel):
    """Estados financieros mas las referencias del sector a comparar."""

    estados: "EntradaEstados"
    referencias: dict[str, float] = Field(default_factory=dict)


@app.post("/api/benchmark", tags=["analisis"])
def benchmark(entrada: EntradaBenchmark):
    """Compara los indicadores contra las referencias del sector dadas.

    Las referencias son un dato externo: no se deducen de los estados
    financieros. Un indicador sin referencia se reporta como no comparado,
    nunca se rellena con un supuesto.
    """
    try:
        ef = EstadosFinancieros(entrada.estados.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return comparar(calcular_todos(ef), entrada.referencias)


# ------------------------------------------------- evaluacion de proyectos


class EntradaProyecto(BaseModel):
    """Un proyecto de inversión a evaluar.

    La inversión viaja aparte de los flujos y como número positivo: el motor
    le pone el signo. Confundir ese signo es el error más comun del tema.
    """

    nombre: str = "Proyecto sin nombre"
    inversion: float = Field(gt=0, description="Inversión inicial, positiva")
    flujos: list[float] = Field(min_length=1, max_length=60)
    tasa_descuento: float = Field(gt=-1, le=10, description="WACC en tanto por uno")
    plazo_exigido: float | None = Field(default=None, gt=0)
    moneda: str = "COP"
    unidad: str = "millones"


class EntradaWacc(BaseModel):
    patrimonio: float | None = None
    deuda: float | None = None
    costo_patrimonio: float | None = None
    costo_deuda: float | None = None
    tasa_impuestos: float | None = None


class EntradaFlujoMensual(BaseModel):
    saldo_inicial: float = 0.0
    meses: list[dict] = Field(default_factory=list, max_length=36)


@app.post("/api/proyecto/evaluar", tags=["proyectos"])
def evaluar(entrada: EntradaProyecto):
    """Evalua un proyecto: VPN, TIR, TIRM, payback, IR, escenarios y veredicto.

    Todo determinista. La IA no interviene: recibe estos números ya resueltos
    si después se le pide redactar el concepto.
    """
    proyecto = Proyecto(**entrada.model_dump())
    return evaluar_proyecto(proyecto)


@app.post("/api/proyecto/wacc", tags=["proyectos"])
def wacc(entrada: EntradaWacc):
    """Costo promedio ponderado de capital, la tasa con la que se descuenta.

    Si falta un insumo lo reporta en vez de suponerlo: un WACC inventado
    contamina todos los indicadores del proyecto.
    """
    return calcular_wacc(**entrada.model_dump())


@app.post("/api/proyecto/flujo-mensual", tags=["proyectos"])
def flujo_mensual(entrada: EntradaFlujoMensual):
    """Flujo de caja a 12 meses con deteccion de faltantes de liquidez.

    Un proyecto puede tener VPN positivo y aún así quebrar la empresa si la
    caja se agota a mitad de año. Esto es lo que detecta ese descalce.
    """
    try:
        return flujo_caja_mensual(entrada.saldo_inicial, entrada.meses)
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, f"Los meses no tienen el formato esperado: {exc}") from exc


@app.post("/api/proyecto/narrar", tags=["ia"])
def narrar_proyecto(entrada: EntradaProyecto):
    """Redacta el concepto de viabilidad del proyecto en prosa.

    Igual que el resto: el motor decide si es viable, el modelo solo lo
    explica. Si el modelo no esta disponible, la evaluación numerica sigue
    sirviendo y se devuelve igual.
    """
    evaluacion = evaluar_proyecto(Proyecto(**entrada.model_dump()))
    try:
        return narrativa.narrar_proyecto(evaluacion)
    except Exception as exc:                     # noqa: BLE001
        raise HTTPException(502, _falla_de_ia(exc)) from exc


# ------------------------------------------------------------------ interfaz

if FRONTEND.exists():
    @app.get("/", include_in_schema=False)
    def inicio():
        return FileResponse(FRONTEND / "index.html")

    app.mount("/", StaticFiles(directory=FRONTEND), name="frontend")
