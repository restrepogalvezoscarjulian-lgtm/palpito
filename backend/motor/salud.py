"""Puntaje de salud financiera (0-100).

Un score sin metodologia visible no se puede defender: es un numero que hay
que creer. Por eso este modulo no esconde nada. Cada indicador que entra al
puntaje viaja con su escala completa, la justificacion del umbral y la fuente
bibliografica, y todo eso se sirve al frontend para pintarlo al lado de la
nota. Quien no este de acuerdo con un umbral puede senalar exactamente cual.

Como se arma la nota de cada indicador:

    nota = 70% x nivel + 30% x tendencia

  - NIVEL: que tan lejos esta el valor del ultimo periodo de un rango
    considerado sano por la bibliografia. Se interpola linealmente entre los
    puntos de una escala, para que no haya saltos bruscos: una razon corriente
    de 1,49 no puede sacar 40 y una de 1,51 sacar 85.
  - TENDENCIA: si mejoro o empeoro entre el primer periodo y el ultimo, medido
    en variacion relativa y orientado segun lo que sea deseable en cada caso
    (en el ciclo de caja bajar es mejorar).

La nota de cada dimension es el promedio ponderado de sus indicadores, y el
puntaje final el promedio ponderado de las dimensiones.

Si falta un dato, ese criterio no puntua cero: se excluye y su peso se reparte
entre los que si tienen dato. Castigar por un dato ausente seria confundir
"no informado" con "malo". Lo excluido se reporta.

Determinista, sin intervencion de ningun modelo de lenguaje.
Criterios y fuentes en FORMULAS.md.
"""

from __future__ import annotations

from dataclasses import dataclass

from .modelos import EstadosFinancieros
from .indicadores import BAENA, CARTILLA, GARCIA, calcular_todos
from .validacion import semaforo, validar

PESO_NIVEL = 0.70
PESO_TENDENCIA = 0.30

# Escala de la tendencia: variacion relativa del indicador, ya orientada de modo
# que positivo siempre signifique "mejoro". Un cambio menor al 5% se considera
# ruido y se queda cerca del punto neutro.
ESCALA_TENDENCIA = ((-0.30, 0.0), (-0.10, 25.0), (-0.02, 45.0), (0.0, 50.0),
                    (0.02, 55.0), (0.10, 75.0), (0.30, 100.0))

BANDAS = (
    (80.0, "Solida", "verde"),
    (60.0, "Aceptable con reservas", "ambar"),
    (40.0, "Fragil", "ambar"),
    (0.0, "Critica", "rojo"),
)


@dataclass(frozen=True)
class Criterio:
    """Un indicador que participa en el puntaje, con su regla de calificacion."""

    codigo: str
    dimension: str
    peso: float                       # peso relativo dentro de su dimension
    escala: tuple                     # puntos (valor, puntaje 0-100), valor creciente
    justificacion: str                # por que ese umbral y no otro
    fuente: str
    mejora: str = "sube"              # "sube" o "baja": que direccion es mejorar
    derivado: str = ""                # si no es un indicador directo, como se obtiene


# ------------------------------------------------------------------ criterios
#
# Los umbrales salen de la bibliografia del curso. Donde la bibliografia da un
# rango y no un punto, la escala premia el centro del rango: tanto quedarse
# corto como pasarse tienen costo. Una razon corriente de 5 no es "salud
# perfecta", es plata ociosa, y Garcia insiste en ese punto.

CRITERIOS: tuple[Criterio, ...] = (
    Criterio(
        codigo="razon_corriente", dimension="Liquidez", peso=60,
        escala=((0.5, 0), (1.0, 45), (1.5, 85), (2.0, 100), (3.0, 80), (5.0, 55)),
        justificacion="Por debajo de 1 la empresa no alcanza a cubrir el pasivo corriente "
                      "con el activo corriente. El rango sano se ubica entre 1,5 y 2 veces. "
                      "Por encima de 3 la nota baja: el exceso de activo corriente es "
                      "capital ocioso que no esta produciendo.",
        fuente=CARTILLA,
    ),
    Criterio(
        codigo="prueba_acida", dimension="Liquidez", peso=40,
        escala=((0.3, 0), (0.7, 45), (1.0, 90), (1.5, 100), (2.5, 75)),
        justificacion="Mide lo mismo sin contar el inventario, que es el activo corriente "
                      "mas lento de volverse caja. Se considera sana a partir de 1 vez: la "
                      "empresa paga sin tener que vender mercancia a las carreras.",
        fuente=BAENA,
    ),
    Criterio(
        codigo="ciclo_conversion_efectivo", dimension="Actividad", peso=45,
        escala=((0, 100), (30, 88), (60, 70), (90, 48), (120, 28), (180, 5)),
        justificacion="Dias que la plata pasa fuera de la caja. Entre mas largo, mas capital "
                      "de trabajo hay que financiar, y esa financiacion cuesta. Un ciclo "
                      "negativo o cercano a cero es la mejor posicion posible: el proveedor "
                      "financia la operacion.",
        fuente=GARCIA, mejora="baja",
    ),
    Criterio(
        codigo="pkt", dimension="Actividad", peso=30,
        escala=((0, 100), (10, 85), (20, 65), (30, 45), (50, 15)),
        justificacion="Centavos de capital de trabajo que exige cada peso de venta. Garcia "
                      "lo usa para saber si crecer conviene: con una PKT alta, vender mas "
                      "consume mas caja de la que produce.",
        fuente=GARCIA, mejora="baja",
    ),
    Criterio(
        codigo="rotacion_activos", dimension="Actividad", peso=25,
        escala=((0.3, 0), (0.8, 45), (1.2, 75), (2.0, 95), (3.0, 100)),
        justificacion="Pesos de venta que genera cada peso de activo. Es el segundo factor "
                      "del sistema DuPont y mide eficiencia pura, sin importar el margen.",
        fuente=CARTILLA,
    ),
    Criterio(
        codigo="endeudamiento_activo", dimension="Endeudamiento", peso=45,
        escala=((0, 85), (30, 100), (50, 80), (60, 55), (70, 30), (85, 5)),
        justificacion="Porcentaje del activo financiado por terceros. Se considera manejable "
                      "hasta 50-60%. Cero deuda tampoco saca la nota maxima: la deuda barata "
                      "y bien usada apalanca la rentabilidad del socio.",
        fuente=BAENA, mejora="baja",
    ),
    Criterio(
        codigo="cobertura_intereses", dimension="Endeudamiento", peso=55,
        escala=((0, 0), (1.0, 20), (2.0, 45), (3.0, 70), (5.0, 90), (8.0, 100)),
        justificacion="Cuantas veces la utilidad operacional alcanza a pagar los intereses. "
                      "Por debajo de 2 veces es zona de riesgo: cualquier tropiezo de la "
                      "operacion deja a la empresa sin con que pagarle al banco.",
        fuente=GARCIA,
    ),
    Criterio(
        codigo="margen_operacional", dimension="Rentabilidad", peso=35,
        escala=((-5, 0), (0, 25), (5, 55), (10, 78), (15, 92), (25, 100)),
        justificacion="El margen del negocio en si, sin contar como esta financiado. Garcia "
                      "lo considera el renglon mas importante del estado de resultados: es "
                      "el unico que depende solo de la operacion.",
        fuente=BAENA,
    ),
    Criterio(
        codigo="margen_neto", dimension="Rentabilidad", peso=30,
        escala=((-3, 0), (0, 30), (3, 55), (7, 80), (12, 95), (20, 100)),
        justificacion="Lo que finalmente queda para los socios despues de intereses e "
                      "impuestos. La distancia con el margen operacional mide cuanto se "
                      "lleva la financiacion.",
        fuente=BAENA,
    ),
    Criterio(
        codigo="roe", dimension="Rentabilidad", peso=35,
        escala=((-5, 0), (0, 25), (8, 55), (15, 80), (25, 95), (40, 100)),
        justificacion="Lo que gana el socio por cada peso metido en la empresa. El piso de "
                      "referencia es lo que ese mismo dinero rendiria sin riesgo; por debajo "
                      "de ahi, el socio esta financiando un negocio que no lo compensa.",
        fuente=CARTILLA,
    ),
    Criterio(
        codigo="spread_roic", dimension="Generacion de valor", peso=100,
        escala=((-10, 0), (-3, 20), (0, 45), (3, 70), (8, 90), (15, 100)),
        justificacion="Diferencia entre lo que rinde el capital invertido (ROIC) y lo que "
                      "cuesta la deuda que lo financia. Es la prueba de fuego de Garcia: si "
                      "el negocio rinde menos de lo que cuesta la plata, destruye valor "
                      "aunque el estado de resultados muestre utilidades.",
        fuente=GARCIA,
        derivado="ROIC - Costo implicito de la deuda financiera",
    ),
)

# Peso de cada dimension dentro del puntaje final. Suman 100.
PESOS_DIMENSION = {
    "Liquidez": 15.0,
    "Actividad": 20.0,
    "Endeudamiento": 25.0,
    "Rentabilidad": 25.0,
    "Generacion de valor": 15.0,
}

NOMBRES = {
    "razon_corriente": "Razon corriente",
    "prueba_acida": "Prueba acida",
    "ciclo_conversion_efectivo": "Ciclo de conversion de efectivo",
    "pkt": "Productividad del capital de trabajo (PKT)",
    "rotacion_activos": "Rotacion de activos",
    "endeudamiento_activo": "Nivel de endeudamiento",
    "cobertura_intereses": "Cobertura de intereses",
    "margen_operacional": "Margen operacional",
    "margen_neto": "Margen neto",
    "roe": "ROE (rentabilidad del patrimonio)",
    "spread_roic": "ROIC menos costo de la deuda",
}

UNIDADES = {
    "razon_corriente": "veces", "prueba_acida": "veces",
    "ciclo_conversion_efectivo": "dias", "pkt": "%", "rotacion_activos": "veces",
    "endeudamiento_activo": "%", "cobertura_intereses": "veces",
    "margen_operacional": "%", "margen_neto": "%", "roe": "%", "spread_roic": "%",
}


# ----------------------------------------------------------------- utilidades


def interpolar(valor: float, escala) -> float:
    """Puntaje 0-100 de un valor dentro de una escala de puntos (valor, puntaje).

    Fuera de los extremos se aplana en el puntaje del extremo, no se extrapola:
    una cobertura de intereses de 40 veces no puede sacar 300.
    """
    if valor <= escala[0][0]:
        return float(escala[0][1])
    if valor >= escala[-1][0]:
        return float(escala[-1][1])
    for (x0, y0), (x1, y1) in zip(escala, escala[1:]):
        if x0 <= valor <= x1:
            if x1 == x0:
                return float(y0)
            return float(y0 + (y1 - y0) * (valor - x0) / (x1 - x0))
    return float(escala[-1][1])


def _puntaje_tendencia(inicial, final, mejora: str):
    """Nota 0-100 por como evoluciono el indicador entre el primer periodo y el ultimo.

    Se mide en variacion relativa sobre el valor inicial. Si el indicador es de
    los que mejoran bajando (ciclo de caja, endeudamiento), se invierte el signo
    para que positivo siempre signifique "mejoro".
    """
    if inicial is None or final is None or inicial == 0:
        return None
    cambio = (final - inicial) / abs(inicial)
    if mejora == "baja":
        cambio = -cambio
    return interpolar(cambio, ESCALA_TENDENCIA)


def _serie_criterio(codigo: str, indicadores: dict):
    """Valores por periodo del criterio, sea indicador directo o derivado."""
    if codigo != "spread_roic":
        ind = indicadores.get(codigo)
        return list(ind.valores) if ind else None

    roic = indicadores.get("roic")
    costo = indicadores.get("costo_deuda_implicito")
    if roic is None or costo is None:
        return None
    return [None if (r is None or c is None) else r - c
            for r, c in zip(roic.valores, costo.valores)]


def banda(puntaje: float) -> dict:
    """Etiqueta cualitativa del puntaje, con el rango a la vista."""
    anterior = 100.0
    for piso, nombre, color in BANDAS:
        if puntaje >= piso:
            return {"nombre": nombre, "color": color,
                    "rango": f"{piso:.0f} a {anterior:.0f}"}
        anterior = piso
    return {"nombre": "Critica", "color": "rojo", "rango": "0 a 40"}


# ------------------------------------------------------------------ calificar


def _calificar(criterio: Criterio, indicadores: dict) -> dict:
    """Aplica un criterio y devuelve su ficha completa, evaluable o no."""
    serie = _serie_criterio(criterio.codigo, indicadores)
    ficha = {
        "codigo": criterio.codigo,
        "nombre": NOMBRES.get(criterio.codigo, criterio.codigo),
        "unidad": UNIDADES.get(criterio.codigo, ""),
        "dimension": criterio.dimension,
        "peso_en_dimension": criterio.peso,
        "escala": [list(p) for p in criterio.escala],
        "mejora": criterio.mejora,
        "justificacion": criterio.justificacion,
        "fuente": criterio.fuente,
        "derivado": criterio.derivado,
        "valores": serie,
        "valor": None, "nivel": None, "tendencia": None, "nota": None,
        "evaluable": False, "motivo": "",
    }

    if not serie or all(v is None for v in serie):
        ficha["motivo"] = "No hay datos suficientes para calcularlo."
        return ficha

    # Se comparan dos periodos DISTINTOS. Si el indicador solo tiene un dato
    # util (el costo de la deuda, por ejemplo, no existe en el primer periodo),
    # no se inventa una tendencia neutra: se califica solo el nivel.
    vivos = [i for i, v in enumerate(serie) if v is not None]
    i_ini, i_fin = vivos[0], vivos[-1]
    inicial, final = serie[i_ini], serie[i_fin]
    nivel = interpolar(final, criterio.escala)
    tendencia = (_puntaje_tendencia(inicial, final, criterio.mejora)
                 if i_fin > i_ini else None)

    if tendencia is None:
        nota = nivel
        ficha["motivo"] = ("Solo se califica el nivel: no hay dos periodos comparables "
                           "para medir la tendencia.")
    else:
        nota = PESO_NIVEL * nivel + PESO_TENDENCIA * tendencia

    ficha.update({"valor": final, "nivel": round(nivel, 2),
                  "tendencia": None if tendencia is None else round(tendencia, 2),
                  "nota": round(nota, 2), "evaluable": True})
    return ficha


def puntaje_salud(ef: EstadosFinancieros) -> dict:
    """Puntaje 0-100 con toda su metodologia expuesta.

    El resultado incluye, para cada criterio, la escala usada, la justificacion
    del umbral y la fuente, para que el puntaje se pueda auditar renglon por
    renglon sin salir de la aplicacion.
    """
    indicadores = calcular_todos(ef)
    fichas = [_calificar(c, indicadores) for c in CRITERIOS]

    dimensiones = []
    for nombre, peso in PESOS_DIMENSION.items():
        propias = [f for f in fichas if f["dimension"] == nombre]
        vivas = [f for f in propias if f["evaluable"]]
        suma_pesos = sum(f["peso_en_dimension"] for f in vivas)

        if not vivas or suma_pesos == 0:
            dimensiones.append({
                "nombre": nombre, "peso": peso, "puntaje": None, "aporte": None,
                "evaluable": False,
                "motivo": "Ningun indicador de esta dimension tiene datos suficientes.",
                "criterios": propias,
            })
            continue

        # Los pesos se renormalizan sobre los criterios que si tienen dato.
        puntaje = sum(f["nota"] * f["peso_en_dimension"] for f in vivas) / suma_pesos
        for f in vivas:
            f["peso_efectivo"] = round(f["peso_en_dimension"] / suma_pesos * 100, 2)
        dimensiones.append({
            "nombre": nombre, "peso": peso, "puntaje": round(puntaje, 2),
            "aporte": None, "evaluable": True, "motivo": "",
            "criterios": propias,
        })

    vivas = [d for d in dimensiones if d["evaluable"]]
    peso_vivo = sum(d["peso"] for d in vivas)
    if not vivas or peso_vivo == 0:
        return {
            "disponible": False,
            "motivo": "No hay datos suficientes para calificar ninguna dimension.",
            "dimensiones": dimensiones,
        }

    total = sum(d["puntaje"] * d["peso"] for d in vivas) / peso_vivo
    for d in vivas:
        d["peso_efectivo"] = round(d["peso"] / peso_vivo * 100, 2)
        d["aporte"] = round(d["puntaje"] * d["peso"] / peso_vivo, 2)

    excluidos = [{"nombre": f["nombre"], "motivo": f["motivo"]}
                 for f in fichas if not f["evaluable"]]
    luz = semaforo(validar(ef))

    return {
        "disponible": True,
        "puntaje": round(total, 1),
        "banda": banda(total),
        "confiable": luz != "rojo",
        "advertencia": (
            "Los estados financieros tienen inconsistencias sin resolver, asi que este "
            "puntaje se calculo sobre datos que no cuadran. Sirve para ubicar el orden "
            "de magnitud, no para decidir. Revise primero la seccion de calidad de datos."
        ) if luz == "rojo" else "",
        "metodologia": {
            "peso_nivel": round(PESO_NIVEL * 100),
            "peso_tendencia": round(PESO_TENDENCIA * 100),
            "formula": "Nota = 70% x nivel frente al umbral + 30% x tendencia entre periodos",
            "explicacion": (
                "Cada indicador se califica de 0 a 100 interpolando su valor sobre una "
                "escala construida con los umbrales de la bibliografia del curso. La nota "
                "de la dimension es el promedio ponderado de sus indicadores, y el puntaje "
                "final el promedio ponderado de las dimensiones. Los criterios sin datos "
                "se excluyen y su peso se reparte entre los demas, en vez de contar cero."
            ),
            "renormalizacion": round(peso_vivo, 2) != 100.0,
        },
        "dimensiones": dimensiones,
        "excluidos": excluidos,
    }
