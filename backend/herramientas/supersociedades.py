"""Construye las referencias sectoriales desde los datos de Supersociedades.

El benchmark es la unica parte de Palpito que necesita un dato EXTERNO: las
cifras del sector no se deducen de los estados de una empresa. Hasta ahora
habia que digitarlas a mano. Este modulo las calcula.

La idea es que no hace falta un motor nuevo: Palpito ya sabe convertir un
balance en 28 indicadores. Si en vez de un balance se le dan las 61.000
sociedades que le reportan a la Superintendencia, devuelve el benchmark del
pais. La misma maquina que analiza una empresa construye la vara con la que se
la mide.

    CIIU  ->  NITs de ese sector       (dataset 6cat-2gcs)
          ->  balance y resultados     (datasets pfdp-zks5 y prwj-nzxa)
          ->  las 23 cuentas del catalogo
          ->  motor.indicadores        (el mismo de siempre)
          ->  mediana y cuartiles      -> referencias/ciiu-XXXX.json

DECISIONES QUE NO SE DEDUCEN DEL CODIGO
---------------------------------------

**Se mapea por nombre EXACTO, no por subcadena.** Es la diferencia con
importacion.py, y es a proposito. Un PDF trae etiquetas libres y hay que
adivinar; este archivo trae una taxonomia cerrada -73 conceptos en el balance,
28 en resultados-, asi que adivinar no solo sobra: hace dano. Al probar con el
diccionario del importador, "Total de patrimonio y pasivos" -que es el ACTIVO-
entraba como patrimonio por contener esa palabra, y "Acciones propias en
cartera" entraba como cuentas por cobrar. Un benchmark asi sale con cifras
bonitas y falsas, que es justo lo que este proyecto existe para no hacer.

**El diccionario vive aqui y no en importacion.py.** Meter "Total de patrimonio
y pasivos" en el diccionario general contaminaria la lectura de los PDF.

**Mediana y cuartiles, nunca promedio.** En datos financieros siempre hay una
empresa que vendio un activo o que apenas arranco, y un promedio no sobrevive a
eso. Ademas los cuartiles permiten decir "esta en el cuartil superior del
sector", que es como habla un analista, en vez de solo "por encima".

**La descarga esta separada del calculo.** `construir_referencias` recibe los
estados ya armados, asi que se puede probar entera sin internet.

**Se guarda de donde salio.** Anio, numero de empresas, fuente y fecha de
descarga viajan dentro del archivo. Una referencia sin procedencia no se puede
sustentar ante quien pregunte, y entonces no sirve.

FUENTE
------
Portal de datos abiertos de Colombia (www.datos.gov.co), conjuntos publicados
por la Superintendencia de Sociedades. Consulta publica, sin registro.
"""

from __future__ import annotations

import json
import statistics as st
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import quote

from motor.indicadores import calcular_todos
from motor.modelos import EstadosFinancieros

PORTAL = "https://www.datos.gov.co/resource"
DATASET_EMPRESAS = "6cat-2gcs"      # 10.000 empresas mas grandes: NIT -> CIIU
DATASET_BALANCE = "pfdp-zks5"       # Estado de situacion financiera
DATASET_RESULTADOS = "prwj-nzxa"    # Estado de resultado integral

FUENTE = ("Superintendencia de Sociedades, vía el portal de datos abiertos de "
          "Colombia (datos.gov.co). Consulta pública.")

# ---------------------------------------------------------------- diccionario
#
# Nombre EXACTO del concepto en la taxonomia -> cuenta del catalogo de Palpito.
# Lo que no este aqui se ignora: es preferible una cuenta ausente -que el motor
# reporta como "sin dato"- a una cuenta mal llenada.

CONCEPTOS_BALANCE: dict[str, str] = {
    "Efectivo y equivalentes al efectivo": "efectivo",
    "Cuentas comerciales por cobrar y otras cuentas por cobrar corrientes": "cuentas_por_cobrar",
    "Inventarios corrientes": "inventarios",
    "Activos corrientes totales": "activo_corriente",
    "Propiedades, planta y equipo": "propiedad_planta_equipo",
    "Total de activos": "activo_total",
    "Cuentas por pagar comerciales y otras cuentas por pagar corrientes": "proveedores",
    "Pasivos corrientes totales": "pasivo_corriente",
    "Total de pasivos no corrientes": "pasivo_no_corriente",
    "Total pasivos": "pasivo_total",
    "Patrimonio total": "patrimonio",
    # OJO: "Total de patrimonio y pasivos" NO va. Es el activo total por el otro
    # lado de la ecuacion contable, y contiene la palabra "patrimonio".
    #
    # La deuda financiera tampoco. "Prestamos corrientes" existe, pero en NIIF
    # buena parte de la deuda bancaria se reporta bajo "Otros pasivos
    # financieros corrientes", que tambien recoge derivados y otras cosas que no
    # son deuda. Sumarlos sobrestimaria el endeudamiento, que es exactamente el
    # error que costo el 66% en Grupo Argos. Los indicadores que dependen de
    # ella se reportan sin dato, igual que para Almacenes Exito.
}

CONCEPTOS_RESULTADOS: dict[str, str] = {
    "Ingresos de actividades ordinarias": "ventas",
    "Costo de ventas": "costo_ventas",
    "Ganancia bruta": "utilidad_bruta",
    "Ganancia (pérdida) por actividades de operación": "utilidad_operacional",
    "Costos financieros": "gastos_financieros",
    "Ganancia (pérdida), antes de impuestos": "utilidad_antes_impuestos",
    "Ingreso (gasto) por impuestos": "impuestos",
    # La taxonomia trae la continuada separada de "Ganancia (perdida)" a secas.
    # Se toma la continuada, que es la decision que ya gobierna todo el motor:
    # la plata de vender un negocio entra una vez y no vuelve.
    "Ganancia (pérdida) procedente de operaciones continuadas": "utilidad_neta",
}

# Cuentas que se suman cuando la taxonomia las reporta partidas.
CONCEPTOS_SUMADOS: dict[str, str] = {
    "Gastos de administración": "gastos_operacionales",
    "Gastos de ventas": "gastos_operacionales",
}


def clave(concepto: str) -> str:
    """Esqueleto ASCII de un concepto, para compararlo pese a las tildes rotas.

    EL PORTAL ENTREGA EL DATO YA CORRUPTO. "Ganancia (perdida) por actividades
    de operacion" llega con la vocal acentuada convertida en el rombo de
    "no pude leer esto": los bytes son literalmente EF BF BD, que es U+FFFD
    codificado en UTF-8. No es un problema de decodificacion de este lado -la
    cabecera dice charset=utf-8 y los bytes son UTF-8 validos- sino del dato en
    origen, perdido antes de publicarse.

    Se comparan los dos lados por su esqueleto ASCII: la vocal acentuada se cae
    del nuestro y el rombo se cae del suyo, y queda la misma cadena. Tampoco se
    puede dar por hecho que SIEMPRE venga roto -si algun dia lo arreglan, el
    esqueleto sigue empatando-, asi que esto aguanta las dos formas.

    Sigue siendo comparacion EXACTA sobre la cadena entera, no por subcadena:
    la razon de existir de este modulo. Una prueba verifica que dos conceptos
    distintos nunca colapsen al mismo esqueleto.
    """
    return " ".join(
        "".join(c for c in concepto.lower() if c.isascii() and (c.isalnum() or c == " ")).split()
    )


# Los diccionarios de arriba se escriben con sus tildes -son para leerlos-, y
# se indexan por esqueleto, que es como se consultan.
BALANCE_POR_CLAVE = {clave(k): v for k, v in CONCEPTOS_BALANCE.items()}
RESULTADOS_POR_CLAVE = {clave(k): v for k, v in CONCEPTOS_RESULTADOS.items()}
SUMADOS_POR_CLAVE = {clave(k): v for k, v in CONCEPTOS_SUMADOS.items()}

# Indicadores que tiene sentido publicar como referencia sectorial. Se dejan
# fuera los que dependen de un dato externo (WACC) o de la deuda financiera,
# que este archivo no permite identificar sin adivinar.
INDICADORES_PUBLICABLES = (
    "razon_corriente", "prueba_acida", "razon_efectivo",
    "dias_cartera", "dias_inventario", "dias_proveedores",
    "ciclo_conversion_efectivo", "pkt", "rotacion_activos",
    "endeudamiento_activo", "apalancamiento", "multiplicador_patrimonio",
    "margen_bruto", "margen_operacional", "margen_neto", "roa", "roe",
)

# Un indicador solo se publica si lo pudieron calcular al menos estas empresas.
# Con menos, la mediana dice mas del azar que del sector.
MINIMO_EMPRESAS = 8


@dataclass
class Referencia:
    """Un indicador del sector, con sus cuartiles y cuantas empresas lo sostienen."""

    codigo: str
    p25: float
    mediana: float
    p75: float
    empresas: int

    def como_dict(self) -> dict:
        return {"p25": round(self.p25, 2), "mediana": round(self.mediana, 2),
                "p75": round(self.p75, 2), "empresas": self.empresas}


@dataclass
class Sector:
    """Las referencias de un CIIU en un anio, con su procedencia."""

    ciiu: str
    anio: int
    referencias: dict[str, Referencia] = field(default_factory=dict)
    empresas_consultadas: int = 0
    empresas_usadas: int = 0
    nombre: str = ""

    def como_dict(self) -> dict:
        return {
            "ciiu": self.ciiu,
            "nombre": self.nombre,
            "anio": self.anio,
            "fuente": FUENTE,
            "descargado": date.today().isoformat(),
            "empresas_consultadas": self.empresas_consultadas,
            "empresas_usadas": self.empresas_usadas,
            # Redondeada: una referencia sectorial con siete decimales es
            # ruido, y en la casilla del formulario no cabe.
            "benchmark": {c: round(r.mediana, 2) for c, r in self.referencias.items()},
            "cuartiles": {c: r.como_dict() for c, r in self.referencias.items()},
        }


# ------------------------------------------------------------------ el armado


def armar_estados(filas_balance: list[dict], filas_resultados: list[dict],
                  empresa: str = "", anio: str = "") -> dict:
    """Convierte los renglones de la taxonomia en el formato del motor.

    Cada archivo trae "Periodo Actual" y "Periodo Anterior" del mismo corte, asi
    que UNA consulta da DOS anios. Se usan los dos: el motor necesita al menos
    dos periodos para leer una tendencia, y los dias de cartera e inventario se
    calculan sobre el saldo del periodo.
    """
    balance: dict[str, list] = {}
    resultados: dict[str, list] = {}
    # orden: el anterior primero, para que el ultimo sea el mas reciente
    periodos_taxonomia = ["Periodo Anterior", "Periodo Actual"]

    def llenar(filas, mapa, destino, sumar=False):
        for i, p in enumerate(periodos_taxonomia):
            del_periodo = [f for f in filas if f.get("periodo") == p]
            for f in del_periodo:
                cuenta = mapa.get(clave(f.get("concepto", "")))
                if not cuenta:
                    continue
                try:
                    v = float(f.get("valor"))
                except (TypeError, ValueError):
                    continue
                serie = destino.setdefault(cuenta, [None, None])
                if sumar and serie[i] is not None:
                    serie[i] += v
                else:
                    serie[i] = v

    llenar(filas_balance, BALANCE_POR_CLAVE, balance)
    llenar(filas_resultados, RESULTADOS_POR_CLAVE, resultados)
    llenar(filas_resultados, SUMADOS_POR_CLAVE, resultados, sumar=True)

    n = len(periodos_taxonomia)
    anio_actual = int(anio) if str(anio).isdigit() else 0
    etiquetas = [str(anio_actual - 1), str(anio_actual)] if anio_actual else ["Anterior", "Actual"]

    return {
        "empresa": empresa,
        "periodos": etiquetas,
        "balance": {k: v for k, v in balance.items() if len(v) == n},
        "resultados": {k: v for k, v in resultados.items() if len(v) == n},
        "moneda": "COP",
        "unidad": "miles",
    }


def construir_referencias(estados: list[dict], ciiu: str, anio: int,
                          nombre: str = "") -> Sector:
    """Calcula los cuartiles del sector a partir de los estados ya armados.

    Sin internet: recibe los estados y devuelve el sector. Asi la parte que
    tiene la logica se puede probar entera.
    """
    sector = Sector(ciiu=ciiu, anio=anio, nombre=nombre,
                    empresas_consultadas=len(estados))
    series: dict[str, list[float]] = {c: [] for c in INDICADORES_PUBLICABLES}
    usadas = 0

    for datos in estados:
        try:
            ind = calcular_todos(EstadosFinancieros(datos))
        except Exception:
            # Una empresa con datos rotos no puede tumbar el sector entero.
            continue
        aporto = False
        for codigo in INDICADORES_PUBLICABLES:
            indicador = ind.get(codigo)
            if indicador is None:
                continue
            v = indicador.valores[-1]
            if v is None or v != v or v in (float("inf"), float("-inf")):
                continue
            series[codigo].append(float(v))
            aporto = True
        if aporto:
            usadas += 1

    sector.empresas_usadas = usadas
    for codigo, vs in series.items():
        if len(vs) < MINIMO_EMPRESAS:
            continue
        vs.sort()
        q = st.quantiles(vs, n=4)
        sector.referencias[codigo] = Referencia(
            codigo=codigo, p25=q[0], mediana=q[1], p75=q[2], empresas=len(vs))
    return sector


# --------------------------------------------------------------- la descarga
#
# Todo lo de aqui abajo toca internet. Se mantiene delgado a proposito: pide y
# entrega, sin decidir nada.


def _pedir(url: str, traer) -> list[dict]:
    """Una consulta al portal. `traer` se inyecta para poder probar sin red."""
    return traer(url)


def urls_de_empresas(ciiu: str, anio: int, limite: int = 400) -> str:
    donde = quote(f"a_o_de_corte='{anio}' AND ciiu='{ciiu}'")
    return (f"{PORTAL}/{DATASET_EMPRESAS}.json?$where={donde}"
            f"&$select=nit,raz_n_social,supervisor&$limit={limite}")


def url_de_estados(dataset: str, nit: str, anio: int) -> str:
    corte = f"{anio}-12-31T00:00:00.000"
    return (f"{PORTAL}/{dataset}.json?nit={nit}&fecha_corte={corte}"
            f"&$select=concepto,valor,periodo&$limit=500")


def descargar_sector(ciiu: str, anio: int, traer, nombre: str = "",
                     tope: int | None = None, avisar=None) -> Sector:
    """Descarga un sector completo y devuelve sus referencias.

    `traer` recibe una URL y devuelve la lista de registros. Se pasa desde
    fuera para que las pruebas no necesiten internet.
    """
    empresas = _pedir(urls_de_empresas(ciiu, anio), traer)
    if tope:
        empresas = empresas[:tope]

    estados = []
    for i, e in enumerate(empresas, 1):
        nit = str(e.get("nit", "")).strip()
        if not nit:
            continue
        try:
            bal = _pedir(url_de_estados(DATASET_BALANCE, nit, anio), traer)
            res = _pedir(url_de_estados(DATASET_RESULTADOS, nit, anio), traer)
        except Exception:
            continue
        if not bal:
            # No esta en Supersociedades: normal si la vigila la Superfinanciera.
            continue
        estados.append(armar_estados(bal, res, e.get("raz_n_social", ""), str(anio)))
        if avisar:
            avisar(i, len(empresas), e.get("raz_n_social", ""))

    return construir_referencias(estados, ciiu, anio, nombre)


def guardar(sector: Sector, carpeta) -> str:
    """Escribe el archivo de referencias y devuelve su ruta."""
    import pathlib

    destino = pathlib.Path(carpeta) / f"ciiu-{sector.ciiu.replace('.', '')}.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(sector.como_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8")
    return str(destino)
