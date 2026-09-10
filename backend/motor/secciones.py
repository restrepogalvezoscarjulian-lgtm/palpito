"""Encuentra en qué páginas de un PDF están los estados financieros.

Un informe anual trae los estados en dos o tres páginas y ochenta de notas.
Leerlo entero mezcla las tablas de las notas con el balance, así que hay que
acotar. Pedirle al usuario que abra el PDF y anote las páginas funciona, pero
es un trabajo que la máquina puede hacer sola.

**Por qué esto no usa el modelo de lenguaje.** Un estado financiero siempre se
anuncia con las mismas palabras: "Estado de Situación Financiera", "Total
activo", "Utilidad neta del periodo". Buscarlas es determinista, instantáneo y
gratis, y sobre todo se puede auditar: el resultado dice qué marcadores encontró
en cada página y con cuánta confianza. Un modelo aquí costaría dinero, tardaría
segundos, y podría inventarse una página que no existe.

El modelo sigue haciendo lo que sí requiere criterio: proponer a qué cuenta
corresponde una etiqueta que el diccionario no reconoció. Eso es clasificar un
nombre; esto es buscar un título.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


def _normalizar(texto: str) -> str:
    """Minúsculas y sin tildes, para que "Situación" y "situacion" empaten."""
    sin_tildes = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sin_tildes.lower())


# Títulos con los que un estado financiero se anuncia a sí mismo. Valen mucho
# porque aparecen una sola vez, justo en la página del estado.
TITULOS = {
    "balance": (
        "estado de situacion financiera",
        "estados de situacion financiera",
        "balance general",
        "estado de posicion financiera",
    ),
    "resultados": (
        "estado de resultados",
        "estados de resultados",
        "estado de ganancias y perdidas",
        "estados de ganancias y perdidas",
        "estado del resultado",
        "estado de resultado integral",
    ),
}

# Renglones que solo aparecen dentro de un estado. Valen menos que un título
# porque una nota también puede mencionarlos, pero juntos son concluyentes.
RENGLONES = {
    "balance": (
        "total activo", "total activos", "total pasivo", "total pasivos",
        "total patrimonio", "activo corriente", "pasivo corriente",
        "total pasivo y patrimonio",
    ),
    "resultados": (
        "utilidad bruta", "utilidad operacional", "utilidad neta",
        "costo de ventas", "costos de ventas", "ingresos operacionales",
        "utilidad antes de impuesto", "ganancia neta",
    ),
}

# Un índice nombra todos los estados a la vez, así que dispararía todos los
# marcadores. Se reconoce por su propia forma: líneas de puntos suspensivos.
_PUNTOS = re.compile(r"\.{4,}\s*\d{1,4}\s*$", re.M)

PESO_TITULO = 4
PESO_RENGLON = 1
# Los estados financieros van juntos: el balance, y enseguida el estado de
# resultados. Si los dos "mejores" candidatos aparecen a mucha distancia, no
# son los estados sino notas que los mencionan. En el informe de Ecopetrol
# -cuyos estados van escaneados y por tanto ilegibles- el detector proponia
# balance en la 36 y resultados en la 125: noventa paginas de separacion.
MAX_SEPARACION = 6
# Puntaje mínimo para creer que una página es un estado y no una nota que lo
# menciona. Un título (4) ya alcanza; tres renglones sueltos también.
UMBRAL = 3


@dataclass
class Hallazgo:
    """Lo que se encontró en una página."""

    pagina: int
    clase: str                       # "balance" | "resultados"
    puntaje: int
    marcadores: list[str] = field(default_factory=list)
    es_indice: bool = False


@dataclass
class Bloque:
    """Un estado financiero que ocupa una o varias hojas seguidas.

    El estado de situación financiera de Grupo Argos ocupa tres páginas —los
    activos en la 16, los pasivos en la 17, el patrimonio en la 18—, y repartido
    así ninguna de las tres alcanza el puntaje de una nota del fondo del
    documento que los mencione todos juntos. Puntuando hojas sueltas, una nota
    de la página 82 le ganaba al balance verdadero. Sumando el puntaje de las
    hojas contiguas, el balance recupera el peso que le corresponde.
    """

    clase: str
    paginas: list[int]
    puntaje: int
    marcadores: list[str] = field(default_factory=list)

    @property
    def ini(self) -> int:
        return self.paginas[0]

    @property
    def fin(self) -> int:
        return self.paginas[-1]


def _agrupar(utiles: list[Hallazgo], clase: str) -> list[Bloque]:
    """Junta en un bloque las páginas seguidas que puntúan en la misma clase."""
    bloques: list[Bloque] = []
    for h in sorted((x for x in utiles if x.clase == clase), key=lambda x: x.pagina):
        if bloques and h.pagina == bloques[-1].fin + 1:
            b = bloques[-1]
            b.paginas.append(h.pagina)
            b.puntaje += h.puntaje
            b.marcadores.extend(m for m in h.marcadores if m not in b.marcadores)
        else:
            bloques.append(Bloque(clase, [h.pagina], h.puntaje, list(h.marcadores)))
    return bloques


def _separacion(a: Bloque, b: Bloque) -> int:
    """Páginas que hay entre dos bloques. Cero si se tocan o se solapan."""
    return max(0, max(a.ini, b.ini) - min(a.fin, b.fin))


def _puntuar(texto: str, clase: str) -> tuple[int, list[str]]:
    plano = _normalizar(texto)
    puntaje, encontrados = 0, []
    for titulo in TITULOS[clase]:
        if titulo in plano:
            puntaje += PESO_TITULO
            encontrados.append(titulo)
            break                     # un título por página ya es suficiente
    for renglon in RENGLONES[clase]:
        if renglon in plano:
            puntaje += PESO_RENGLON
            encontrados.append(renglon)
    return puntaje, encontrados


def analizar_paginas(textos: list[str]) -> dict:
    """Recibe el texto de cada página y dice dónde están los estados.

    `textos[i]` es el texto de la página i+1. Devuelve el rango sugerido y todo
    lo que lo sustenta, para que la decisión se pueda auditar en pantalla.
    """
    hallazgos: list[Hallazgo] = []

    for i, texto in enumerate(textos, start=1):
        if not (texto or "").strip():
            continue
        # Un índice menciona todos los estados: hay que sacarlo antes de
        # puntuar, o se llevaría el puntaje más alto del documento.
        es_indice = len(_PUNTOS.findall(texto)) >= 3
        for clase in ("balance", "resultados"):
            puntaje, marcadores = _puntuar(texto, clase)
            if puntaje >= UMBRAL:
                hallazgos.append(Hallazgo(i, clase, puntaje, marcadores, es_indice))

    utiles = [h for h in hallazgos if not h.es_indice]
    descartados_indice = sorted({h.pagina for h in hallazgos if h.es_indice})

    if not utiles:
        return {
            "encontrado": False,
            "paginas": "",
            "lectura": (
                "No se reconocieron las páginas de los estados financieros. "
                "Puede indicarlas a mano, o dejar el campo vacío para leer todo "
                "el documento."
            ),
            "detalle": [],
            "descartados_por_indice": descartados_indice,
        }

    # Las páginas seguidas de la misma clase son un solo estado repartido en
    # varias hojas, no candidatas que compitan entre ellas.
    bloques = {clase: _agrupar(utiles, clase) for clase in ("balance", "resultados")}

    # Los estados financieros van juntos: primero el balance y enseguida el
    # estado de resultados. Así que en vez de elegir el mejor de cada clase por
    # separado y castigar después la distancia, se busca directamente **la
    # pareja vecina** de mayor puntaje combinado. Una nota que hable de activos
    # en la página 82 puede puntuar alto, pero no tiene al lado un estado de
    # resultados que la acompañe; el balance verdadero sí.
    elegidos: list[Bloque] = []
    parejas = [
        (b, r)
        for b in bloques["balance"]
        for r in bloques["resultados"]
        if _separacion(b, r) <= MAX_SEPARACION
    ]
    if parejas:
        b, r = max(parejas, key=lambda p: (p[0].puntaje + p[1].puntaje,
                                           -min(p[0].ini, p[1].ini)))
        elegidos = sorted((b, r), key=lambda x: x.ini)

    # Sin pareja vecina hay dos casos distintos: que el documento solo traiga una
    # de las dos clases (legítimo), o que traiga las dos pero dispersas, que casi
    # siempre significa que solo se están viendo notas.
    disperso = not parejas and bool(bloques["balance"]) and bool(bloques["resultados"])
    if not elegidos:
        todos = bloques["balance"] + bloques["resultados"]
        mejor = max(todos, key=lambda x: (x.puntaje, -x.ini))
        elegidos = [mejor]
        if disperso and mejor.puntaje < PESO_TITULO + 2:
            return {
                "encontrado": False,
                "paginas": "",
                "lectura": (
                    "No se pudo ubicar con confianza donde estan los estados "
                    "financieros: los candidatos aparecen dispersos por el "
                    "documento, lo que suele significar que solo se estan "
                    "encontrando notas que los mencionan. Indique las paginas a "
                    "mano, o deje el campo vacio para leer todo."
                ),
                "detalle": [
                    {"pagina": h.pagina, "clase": h.clase, "puntaje": h.puntaje,
                     "marcadores": h.marcadores}
                    for h in sorted(utiles, key=lambda x: (-x.puntaje, x.pagina))[:12]
                ],
                "descartados_por_indice": descartados_indice,
                "disperso": True,
            }
    # El tramo va del primer bloque al último. Ya no hace falta la página de
    # cola que se agregaba antes: los bloques abarcan el estado completo, y esa
    # cola era justamente lo que salvaba de casualidad el caso de Nutresa.
    ini = min(b.ini for b in elegidos)
    fin = min(max(b.fin for b in elegidos), len(textos))
    rango = f"{ini}-{fin}" if fin > ini else str(ini)

    partes = []
    for b in elegidos:
        nombre = "el balance" if b.clase == "balance" else "el estado de resultados"
        if len(b.paginas) > 1:
            partes.append(f"{nombre} en las páginas {b.ini} a {b.fin}")
        else:
            partes.append(f"{nombre} en la página {b.ini}")
    lectura = "Se reconoció " + " y ".join(partes) + f". Se leerán las páginas {rango}."
    if descartados_indice:
        lectura += (f" Se ignoró la tabla de contenido "
                    f"(página{'s' if len(descartados_indice) > 1 else ''} "
                    f"{', '.join(str(p) for p in descartados_indice)}).")

    return {
        "encontrado": True,
        "paginas": rango,
        "lectura": lectura,
        "detalle": [
            {"pagina": h.pagina, "clase": h.clase, "puntaje": h.puntaje,
             "marcadores": h.marcadores}
            for h in sorted(utiles, key=lambda x: (-x.puntaje, x.pagina))[:12]
        ],
        # Qué bloques se eligieron y con cuánto puntaje, para poder discutir en
        # pantalla por qué el balance de tres hojas le ganó a una nota suelta.
        "bloques": [
            {"clase": b.clase, "paginas": list(b.paginas), "puntaje": b.puntaje,
             "marcadores": b.marcadores}
            for b in elegidos
        ],
        "descartados_por_indice": descartados_indice,
        "disperso": disperso,
    }


def detectar_en_pdf(contenido: bytes) -> dict:
    """Abre el PDF y busca las páginas de los estados financieros."""
    import io

    import pdfplumber

    with pdfplumber.open(io.BytesIO(contenido)) as pdf:
        textos = [(p.extract_text() or "") for p in pdf.pages]
    resultado = analizar_paginas(textos)
    resultado["total_paginas"] = len(textos)
    return resultado
