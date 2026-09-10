"""Comparación de los indicadores contra referencias del sector.

El profesor lo pidió en la sesión 5: "poder comparar por ejemplo contra
benchmarks sectoriales y ver si lo que estamos haciendo está bien o está mal
en la compañía".

Regla que gobierna este módulo, la misma del WACC: **las cifras del sector son
un dato externo y no se inventan**. No se deducen de los estados financieros de
una empresa, hay que traerlas de una fuente (Supersociedades, gremios, DANE) o
digitarlas. Un indicador sin referencia se reporta como "sin referencia", nunca
se compara contra un número supuesto.

Comparar mal es peor que no comparar: una empresa que sale "por encima del
sector" contra una cifra inventada toma decisiones sobre nada.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .modelos import Indicador
from .salud import CRITERIOS

# Dirección de mejora de cada indicador, reutilizada del puntaje de salud para
# que las dos lecturas no puedan contradecirse. Si el puntaje dice que bajar el
# endeudamiento es mejorar, el benchmark no puede decir lo contrario.
MEJORA = {c.codigo: c.mejora for c in CRITERIOS}

# Indicadores que no están en el puntaje pero sí admiten comparación sectorial.
MEJORA_EXTRA = {
    "prueba_acida": "sube",
    "razon_efectivo": "sube",
    "rotacion_activos": "sube",
    "dias_proveedores": "sube",
    "margen_bruto": "sube",
    "margen_operacional": "sube",
    "apalancamiento": "baja",
    "multiplicador_patrimonio": "baja",
    "costo_deuda_implicito": "baja",
    "pkt": "baja",
    "endeudamiento_activo_implicito": "baja",
    "dias_cartera": "baja",
    "dias_inventario": "baja",
    "ciclo_conversion_efectivo": "baja",
    "roa": "sube",
    "roic": "sube",
    "tasa_impuestos": "baja",
    "spread_valor": "sube",
}

# Cuánto hay que separarse de la referencia para que deje de ser "en línea".
# Se expresa en porcentaje de la propia referencia, no en puntos absolutos,
# porque una diferencia de 0,1 significa cosas muy distintas en una razón
# corriente de 1,8 que en un margen de 0,4.
HOLGURA = 0.10


@dataclass
class Comparacion:
    """Un indicador frente a su referencia sectorial."""

    codigo: str
    nombre: str
    unidad: str
    valor: float | None
    referencia: float | None
    brecha: float | None = None          # valor - referencia
    brecha_relativa: float | None = None  # en porcentaje de la referencia
    posicion: str = "sin_referencia"      # "encima" | "en_linea" | "debajo"
    veredicto: str = "sin_referencia"     # "favorable" | "en_linea" | "desfavorable"
    lectura: str = ""
    mejora: str = ""


def _direccion(codigo: str) -> str | None:
    return MEJORA.get(codigo) or MEJORA_EXTRA.get(codigo)


def _texto(nombre: str, posicion: str, veredicto: str,
           brecha_rel: float | None, unidad: str) -> str:
    if posicion == "en_linea":
        return f"{nombre} está en línea con el sector."
    lado = "por encima" if posicion == "encima" else "por debajo"
    cuanto = f" ({abs(brecha_rel):.1f}% {lado})" if brecha_rel is not None else ""
    if veredicto == "favorable":
        return f"{nombre} está {lado} del sector{cuanto}, y en este indicador eso es mejor."
    return f"{nombre} está {lado} del sector{cuanto}, y en este indicador eso es peor."


def comparar_indicador(indicador: Indicador,
                       referencia: float | None) -> Comparacion:
    """Compara el último valor de un indicador contra su referencia.

    Se usa el último periodo y no el promedio porque el benchmark responde a
    "cómo estoy hoy frente al sector", no a "cómo estuve en promedio".
    """
    valor = None
    for v in reversed(indicador.valores):
        if v is not None:
            valor = v
            break

    c = Comparacion(
        codigo=indicador.codigo,
        nombre=indicador.nombre,
        unidad=indicador.unidad,
        valor=valor,
        referencia=referencia,
        mejora=_direccion(indicador.codigo) or "",
    )

    if valor is None:
        c.lectura = f"{indicador.nombre}: la empresa no informa el dato."
        return c
    if referencia is None:
        c.lectura = (f"{indicador.nombre}: no se declaró una referencia del "
                     f"sector, así que no se compara.")
        return c

    c.brecha = valor - referencia
    if referencia != 0:
        c.brecha_relativa = (valor - referencia) / abs(referencia) * 100

    margen = abs(referencia) * HOLGURA
    if abs(c.brecha) <= margen + 1e-9:
        c.posicion, c.veredicto = "en_linea", "en_linea"
    else:
        c.posicion = "encima" if c.brecha > 0 else "debajo"
        direccion = c.mejora
        if not direccion:
            # Sin dirección conocida no se emite juicio: se reporta la posición
            # y se deja que el analista la interprete.
            c.veredicto = "sin_criterio"
            c.lectura = (f"{indicador.nombre} está {'por encima' if c.posicion == 'encima' else 'por debajo'} "
                         f"del sector. Este indicador no tiene una dirección "
                         f"de mejora definida: interprételo según el caso.")
            return c
        mejor_arriba = direccion == "sube"
        c.veredicto = ("favorable"
                       if (c.posicion == "encima") == mejor_arriba
                       else "desfavorable")

    c.lectura = _texto(indicador.nombre, c.posicion, c.veredicto,
                       c.brecha_relativa, c.unidad)
    return c


def comparar(indicadores: dict[str, Indicador],
             referencias: dict[str, float] | None) -> dict:
    """Compara todos los indicadores contra el conjunto de referencias dado.

    `referencias` es {codigo_indicador: valor}. Las que falten se reportan como
    no comparadas; nunca se rellenan.
    """
    referencias = referencias or {}
    comparaciones = []
    for codigo, indicador in indicadores.items():
        # Solo tiene sentido comparar razones y porcentajes: un monto depende
        # del tamano de la empresa y compararlo contra el sector no dice nada.
        if indicador.unidad == "monto":
            continue
        ref = referencias.get(codigo)
        comparaciones.append(comparar_indicador(indicador, ref))

    comparadas = [c for c in comparaciones if c.veredicto in
                  ("favorable", "en_linea", "desfavorable")]
    favorables = sum(1 for c in comparadas if c.veredicto == "favorable")
    en_linea = sum(1 for c in comparadas if c.veredicto == "en_linea")
    desfavorables = sum(1 for c in comparadas if c.veredicto == "desfavorable")

    if not comparadas:
        lectura = ("No se declaró ninguna referencia del sector, así que no hay "
                   "comparación. Las referencias no se pueden deducir de los "
                   "estados financieros de la empresa: hay que traerlas de una "
                   "fuente sectorial o digitarlas.")
    else:
        lectura = (f"Se compararon {len(comparadas)} indicadores contra el "
                   f"sector: {favorables} mejor, {en_linea} en línea y "
                   f"{desfavorables} peor.")

    return {
        "disponible": bool(comparadas),
        "holgura": HOLGURA,
        "comparaciones": [vars(c) for c in comparaciones],
        "total_comparados": len(comparadas),
        "favorables": favorables,
        "en_linea": en_linea,
        "desfavorables": desfavorables,
        "sin_referencia": len(comparaciones) - len(comparadas),
        "lectura": lectura,
        "nota_fuente": (
            "Las referencias sectoriales son un dato externo. En Colombia se "
            "pueden construir con los estados financieros que las empresas "
            "reportan a la Superintendencia de Sociedades, o con los informes "
            "del gremio del sector. Digite la fuente que use para poder "
            "sustentarla."
        ),
    }


def codigos_comparables(indicadores: dict[str, Indicador]) -> list[dict]:
    """Lista de indicadores que admiten referencia, para armar el formulario."""
    salida = []
    for codigo, i in indicadores.items():
        if i.unidad == "monto":
            continue
        salida.append({
            "codigo": codigo,
            "nombre": i.nombre,
            "unidad": i.unidad,
            "categoria": i.categoria,
            "mejora": _direccion(codigo) or "",
        })
    return salida
