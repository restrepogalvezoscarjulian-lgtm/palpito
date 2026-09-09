"""Lectura de estados financieros desde Excel, CSV y PDF.

El problema de importar no es abrir el archivo: es que cada empresa nombra sus
cuentas distinto. "Deudores comerciales", "Cartera clientes" y "CxC" son la
misma cosa, y el motor necesita un codigo exacto para calcular.

Por eso la importacion tiene dos etapas separadas a proposito:

  1. LECTURA (este modulo, deterministica): abre el archivo, arma una tabla de
     filas con etiqueta y cifras, detecta los periodos y propone un mapeo con
     un diccionario de sinonimos escrito a mano.
  2. CONFIRMACION (el usuario, en pantalla): lo que el diccionario no reconoce
     se le puede pasar a un modelo para que PROPONGA a que cuenta corresponde
     (ver narrativa.proponer_cuentas). Esa propuesta nunca se aplica sola: se
     muestra marcada, con su confianza y con quien la hizo, y el usuario
     confirma o corrige antes de que se calcule nada.

La regla de la aplicacion se mantiene intacta: el modelo puede opinar sobre
COMO SE LLAMA una fila, jamas sobre cuanto vale ni sobre que significa. Los
numeros salen del archivo y los calculos, del motor.
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from dataclasses import asdict, dataclass, field

# Cuentas que entienden los modelos del motor, agrupadas como las espera
# EstadosFinancieros. El orden es el de presentacion en pantalla.
CUENTAS_BALANCE = [
    "efectivo", "cuentas_por_cobrar", "inventarios", "activo_corriente",
    "propiedad_planta_equipo", "activo_total", "proveedores",
    "deuda_financiera_cp", "pasivo_corriente", "deuda_financiera_lp",
    "patrimonio",
]
CUENTAS_RESULTADOS = [
    "ventas", "costo_ventas", "utilidad_bruta", "gastos_operacionales",
    "utilidad_operacional", "gastos_financieros", "utilidad_antes_impuestos",
    "impuestos", "utilidad_neta", "depreciacion", "compras", "ventas_credito",
]
CUENTAS = CUENTAS_BALANCE + CUENTAS_RESULTADOS

GRUPO = {c: "balance" for c in CUENTAS_BALANCE}
GRUPO.update({c: "resultados" for c in CUENTAS_RESULTADOS})

# Diccionario de sinonimos. Se compara sobre el texto normalizado (sin tildes,
# en minusculas). Cada entrada es una frase que debe aparecer completa dentro
# de la etiqueta de la fila. Se evalua de la mas larga a la mas corta, para que
# "utilidad antes de impuestos" gane sobre "utilidad".
SINONIMOS: dict[str, tuple[str, ...]] = {
    "efectivo": ("efectivo y equivalentes", "efectivo", "caja y bancos", "caja",
                 "bancos", "disponible"),
    "cuentas_por_cobrar": ("cuentas por cobrar", "deudores comerciales", "deudores",
                           "cartera clientes", "cartera", "clientes", "cxc"),
    "inventarios": ("inventarios", "inventario", "existencias", "mercancias",
                    "mercancia"),
    "activo_corriente": ("total activo corriente", "activo corriente",
                         "activos corrientes", "total corriente activo"),
    "propiedad_planta_equipo": ("propiedad planta y equipo", "propiedades planta y equipo",
                                "propiedad planta", "activos fijos", "activo fijo",
                                "ppe", "planta y equipo"),
    "activo_total": ("total activo", "total activos", "activo total", "activos totales",
                     "suma del activo"),
    "proveedores": ("proveedores", "cuentas por pagar proveedores",
                    "acreedores comerciales", "cuentas por pagar comerciales"),
    "deuda_financiera_cp": ("obligaciones financieras corto plazo",
                            "obligaciones financieras cp", "deuda financiera corto plazo",
                            "deuda financiera cp", "creditos corto plazo",
                            "obligaciones bancarias corto plazo"),
    "pasivo_corriente": ("total pasivo corriente", "pasivo corriente",
                         "pasivos corrientes", "total corriente pasivo"),
    "deuda_financiera_lp": ("obligaciones financieras largo plazo",
                            "obligaciones financieras lp", "deuda financiera largo plazo",
                            "deuda financiera lp", "pasivo no corriente",
                            "pasivos no corrientes", "creditos largo plazo",
                            "obligaciones bancarias largo plazo"),
    "patrimonio": ("total patrimonio", "patrimonio neto", "patrimonio",
                   "capital contable"),
    "ventas": ("ingresos operacionales", "ingresos por ventas", "ingresos de actividades",
               "ventas netas", "ventas", "ingresos"),
    "costo_ventas": ("costo de ventas", "costo de la mercancia vendida",
                     "costo de mercancia vendida", "costos de ventas", "costo ventas"),
    "utilidad_bruta": ("utilidad bruta", "ganancia bruta", "margen bruto en pesos"),
    "gastos_operacionales": ("gastos de administracion y ventas", "gastos operacionales",
                             "gastos de operacion", "gastos administrativos y de ventas",
                             "gastos administracion y ventas"),
    "utilidad_operacional": ("utilidad operacional", "utilidad de operacion",
                             "resultado operacional", "ganancia operacional",
                             "utilidad antes de intereses e impuestos", "uaii", "ebit"),
    "gastos_financieros": ("gastos financieros", "intereses pagados",
                           "costos financieros", "gasto por intereses", "intereses"),
    "utilidad_antes_impuestos": ("utilidad antes de impuestos", "utilidad antes de impuesto",
                                 "resultado antes de impuestos", "uai",
                                 "ganancia antes de impuestos"),
    "impuestos": ("impuesto de renta", "impuesto sobre la renta", "provision de impuestos",
                  "impuestos", "impuesto"),
    "utilidad_neta": ("utilidad neta", "ganancia neta", "resultado del ejercicio",
                      "resultado neto", "utilidad del ejercicio"),
    "depreciacion": ("depreciacion y amortizacion", "depreciacion", "amortizacion"),
    "compras": ("compras del periodo", "compras"),
    "ventas_credito": ("ventas a credito", "ventas credito"),
}

# Filas que nunca son una cuenta: encabezados, totales de control, notas.
RUIDO = ("cuenta", "concepto", "descripcion", "rubro", "nota", "notas",
         "estado de situacion", "estado de resultados", "balance general",
         "cifras en", "expresado en", "variacion", "analisis", "%")

MAX_PERIODOS = 6


@dataclass
class Fila:
    """Una linea del archivo: su etiqueta original y las cifras que traia."""

    etiqueta: str
    valores: list
    origen: str = ""            # hoja o pagina de donde salio
    cuenta: str | None = None   # codigo asignado
    grupo: str = ""             # balance o resultados
    asignado_por: str = ""      # "diccionario", "modelo" o "usuario"
    confianza: str = ""         # alta, media o baja
    nota: str = ""


@dataclass
class Tabla:
    """Lo que se logro leer del archivo, antes de que nadie confirme nada."""

    periodos: list[str] = field(default_factory=list)
    filas: list[Fila] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    origen: str = ""

    def como_dict(self) -> dict:
        return {
            "periodos": self.periodos,
            "filas": [asdict(f) for f in self.filas],
            "avisos": self.avisos,
            "origen": self.origen,
        }


# ------------------------------------------------------------ texto y numeros


def normalizar(texto: str) -> str:
    """Minusculas, sin tildes y sin puntuacion, para poder comparar etiquetas."""
    if texto is None:
        return ""
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.lower().replace("$", " ")
    t = re.sub(r"[^\w\s%]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def leer_numero(bruto):
    """Interpreta una celda como cifra, o devuelve None si no lo es.

    Tiene que aguantar lo que sale de una contabilidad colombiana:

        "1.234.567,89"   -> 1234567.89   (punto de miles, coma decimal)
        "1,234,567.89"   -> 1234567.89   (formato ingles)
        "$ 2.450"        -> 2450.0
        "(550)"          -> -550.0       (parentesis = negativo)
        "1.234"          -> 1234.0       (miles, no un decimal)
        "-", "", "n/d"   -> None         (dato ausente, NO cero)

    Un dato ausente jamas se convierte en cero: el motor distingue "no
    informado" de "vale cero" y todo el diagnostico depende de eso.
    """
    if bruto is None:
        return None
    if isinstance(bruto, bool):
        return None
    if isinstance(bruto, (int, float)):
        return float(bruto)

    t = str(bruto).strip()
    if not t:
        return None

    negativo = t.startswith("(") and t.endswith(")")
    t = t.strip("()").replace("$", "").replace("COP", "").replace("%", "")
    t = t.replace(" ", " ").replace(" ", "")
    if not t or t in {"-", "--", "n/d", "nd", "na", "n/a", "."}:
        return None
    if t.startswith("-"):
        negativo = True
        t = t[1:]
    if not re.fullmatch(r"[\d.,]+", t):
        return None

    coma, punto = t.rfind(","), t.rfind(".")
    if coma >= 0 and punto >= 0:
        # El separador decimal es el que aparece de ultimo.
        if coma > punto:
            t = t.replace(".", "").replace(",", ".")
        else:
            t = t.replace(",", "")
    elif coma >= 0:
        # Una sola coma: decimal si deja uno o dos digitos ("2,5"), miles si no.
        t = t.replace(",", "." if len(t) - coma - 1 <= 2 else "")
    elif punto >= 0:
        # Un solo punto con exactamente tres digitos detras es miles: "1.234".
        if len(t) - punto - 1 == 3:
            t = t.replace(".", "")
    try:
        valor = float(t)
    except ValueError:
        return None
    return -valor if negativo else valor


def parece_periodo(texto) -> str | None:
    """Reconoce un encabezado de columna que nombre un periodo.

    Acepta un ano suelto (2024), un ano con adornos (FY2024, Dic-2024) y
    rangos cortos. Devuelve el periodo ya limpio, o None.
    """
    if texto is None:
        return None
    t = str(texto).strip()
    if not t:
        return None
    anios = re.findall(r"(19|20)\d{2}", t)
    if not anios:
        return None
    completo = re.findall(r"(?:19|20)\d{2}", t)
    if len(completo) == 1 and len(t) <= 24:
        return t if len(t) <= 12 else completo[0]
    return completo[-1]


# --------------------------------------------------------------- diccionario


def _frases_ordenadas():
    """Sinonimos de la frase mas larga a la mas corta, con su cuenta."""
    pares = [(frase, cuenta) for cuenta, frases in SINONIMOS.items() for frase in frases]
    return sorted(pares, key=lambda p: -len(p[0]))


FRASES = _frases_ordenadas()


def buscar_cuenta(etiqueta: str):
    """Cuenta que corresponde a una etiqueta segun el diccionario.

    Devuelve (codigo, confianza) o (None, ""). La confianza es alta cuando la
    etiqueta es practicamente el nombre de la cuenta, y media cuando el
    sinonimo aparece dentro de un texto mas largo, donde puede haber trampa
    ("total activo corriente" contiene "activo corriente" pero tambien
    "corriente" a secas).
    """
    limpia = normalizar(etiqueta)
    if not limpia or limpia in RUIDO:
        return None, ""
    for frase, cuenta in FRASES:
        if limpia == frase:
            return cuenta, "alta"
    for frase, cuenta in FRASES:
        if re.search(r"\b" + re.escape(frase) + r"\b", limpia):
            sobra = len(limpia) - len(frase)
            return cuenta, "alta" if sobra <= 6 else "media"
    return None, ""


def mapear(tabla: Tabla) -> Tabla:
    """Asigna cuentas a las filas con el diccionario, sin tocar los numeros.

    Si dos filas reclaman la misma cuenta se conserva la de mejor confianza y
    la otra queda libre, con una nota que lo explica. Adivinar en silencio ahi
    seria la forma mas facil de arruinar un balance.
    """
    tomadas: dict[str, Fila] = {}
    for fila in tabla.filas:
        cuenta, confianza = buscar_cuenta(fila.etiqueta)
        if not cuenta:
            continue
        previa = tomadas.get(cuenta)
        if previa is None:
            fila.cuenta, fila.confianza, fila.asignado_por = cuenta, confianza, "diccionario"
            fila.grupo = GRUPO[cuenta]
            tomadas[cuenta] = fila
            continue
        # Ya habia una fila para esa cuenta: gana la de confianza alta.
        if confianza == "alta" and previa.confianza != "alta":
            previa.cuenta, previa.grupo, previa.asignado_por = None, "", ""
            previa.nota = (f"Otra fila se identifico mejor como {cuenta}. "
                           "Reviselo si esta fila era la correcta.")
            previa.confianza = ""
            fila.cuenta, fila.confianza, fila.asignado_por = cuenta, confianza, "diccionario"
            fila.grupo = GRUPO[cuenta]
            tomadas[cuenta] = fila
        else:
            fila.nota = (f"Se parece a {cuenta}, pero esa cuenta ya la tomo la fila "
                         f"\"{previa.etiqueta}\". Elija cual de las dos es.")
    return tabla


# -------------------------------------------------------------------- lectura


def _filas_desde_matriz(matriz, origen: str, tabla: Tabla,
                        fusionar_continuaciones: bool = False) -> None:
    """Convierte una matriz de celdas en filas con etiqueta y cifras.

    La primera columna que trae texto es la etiqueta; las columnas numericas
    son los periodos, en el orden en que aparecen. Se detectan los encabezados
    de periodo en las primeras filas.
    """
    if not matriz:
        return

    # Encabezado: la primera fila donde aparezcan periodos y TODA cifra sea un
    # ano. Un "2024" se lee como numero, asi que no sirve exigir que la fila no
    # tenga cifras: hay que exigir que las que tenga sean todas periodos. Si la
    # etiqueta de la fila ya es una cuenta conocida, no es encabezado sino
    # datos (una fila "Ventas | 2023 | 2024" no puede pasar por titulo).
    encabezado, periodos = None, []
    for i, fila in enumerate(matriz[:8]):
        limpios = [p for p in (parece_periodo(c) for c in fila) if p]
        if not limpios:
            continue
        numericas = [c for c in fila if leer_numero(c) is not None]
        if not all(parece_periodo(c) for c in numericas):
            continue
        etiqueta = next((c for c in fila if c is not None and str(c).strip()
                         and leer_numero(c) is None), "")
        if etiqueta and buscar_cuenta(str(etiqueta))[0]:
            continue
        encabezado, periodos = i, limpios[:MAX_PERIODOS]
        break

    if periodos and not tabla.periodos:
        tabla.periodos = periodos

    inicio = 0 if encabezado is None else encabezado + 1
    for fila in matriz[inicio:]:
        # Una celda puede traer su texto partido en varias lineas: se une.
        celdas = [None if c is None else str(c).replace("\n", " ").strip()
                  if isinstance(c, str) else c for c in fila]
        etiqueta = next((str(c).strip() for c in celdas
                         if c is not None and str(c).strip()
                         and leer_numero(c) is None), "")
        if not etiqueta:
            continue
        numeros = [leer_numero(c) for c in celdas]
        numeros = [n for n in numeros if n is not None]
        if not numeros:
            # Renglon sin cifras. En un PDF suele ser la segunda linea de un
            # nombre largo ("Efectivo y" / "equivalentes"), que el extractor
            # parte en dos. Se pega a la fila anterior en vez de perderse.
            if (fusionar_continuaciones and tabla.filas
                    and len(etiqueta.split()) <= 4
                    and not buscar_cuenta(etiqueta)[0]):
                anterior = tabla.filas[-1]
                if anterior.origen == origen:
                    anterior.etiqueta = f"{anterior.etiqueta} {etiqueta}".strip()
            continue
        tabla.filas.append(Fila(etiqueta=etiqueta,
                                valores=numeros[:MAX_PERIODOS],
                                origen=origen))


def leer_excel(contenido: bytes, tabla: Tabla) -> None:
    from openpyxl import load_workbook

    libro = load_workbook(io.BytesIO(contenido), data_only=True, read_only=True)
    for hoja in libro.worksheets:
        matriz = [list(f) for f in hoja.iter_rows(values_only=True)]
        _filas_desde_matriz(matriz, hoja.title, tabla)
    libro.close()
    if len(libro.sheetnames) > 1:
        tabla.avisos.append(
            f"El archivo trae {len(libro.sheetnames)} hojas y se leyeron todas. "
            "Revise que no se hayan mezclado cuentas de hojas distintas.")


def leer_csv(contenido: bytes, tabla: Tabla) -> None:
    texto = None
    for codificacion in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            texto = contenido.decode(codificacion)
            break
        except UnicodeDecodeError:
            continue
    if texto is None:
        raise ValueError("No se pudo leer el archivo de texto.")
    try:
        dialecto = csv.Sniffer().sniff(texto[:4000], delimiters=";,\t|")
        delimitador = dialecto.delimiter
    except csv.Error:
        delimitador = ";" if texto.count(";") > texto.count(",") else ","
    matriz = [f for f in csv.reader(io.StringIO(texto), delimiter=delimitador)]
    _filas_desde_matriz(matriz, "csv", tabla)


def leer_pdf(contenido: bytes, tabla: Tabla) -> None:
    """Extrae tablas de un PDF, y si no hay, cae al texto linea por linea.

    Un PDF no tiene celdas: la tabla hay que reconstruirla. Por eso esta via
    siempre deja un aviso pidiendo revision, y por eso ninguna cifra entra al
    calculo sin que el usuario la confirme en pantalla.
    """
    import pdfplumber

    encontro_tabla = False
    with pdfplumber.open(io.BytesIO(contenido)) as pdf:
        if not pdf.pages:
            raise ValueError("El PDF no tiene paginas legibles.")
        for n, pagina in enumerate(pdf.pages, start=1):
            for matriz in pagina.extract_tables() or []:
                if matriz and len(matriz) > 1:
                    encontro_tabla = True
                    _filas_desde_matriz(matriz, f"pagina {n}", tabla)
            if not encontro_tabla:
                texto = pagina.extract_text() or ""
                matriz = [_partir_linea(l) for l in texto.splitlines() if l.strip()]
                _filas_desde_matriz([m for m in matriz if m], f"pagina {n} (texto)",
                                    tabla, fusionar_continuaciones=True)

    if encontro_tabla:
        tabla.avisos.append(
            "Las cifras se reconstruyeron de las tablas del PDF. Un PDF no guarda "
            "celdas, asi que compare cada renglon contra el documento original "
            "antes de confirmar.")
    else:
        tabla.avisos.append(
            "El PDF no traia tablas reconocibles y se leyo como texto suelto, que "
            "es la via mas fragil. Revise renglon por renglon. Si el PDF es una "
            "imagen escaneada, no habra cifras y toca digitarlas o conseguir el Excel.")


def _partir_linea(linea: str):
    """Separa una linea de texto de PDF en etiqueta y cifras.

    Las cifras van pegadas al final del renglon separadas por espacios; el
    resto es el nombre de la cuenta.
    """
    texto = linea.strip()
    piezas = re.split(r"\s{2,}|\t", texto)
    if len(piezas) > 1:
        return [p.strip() for p in piezas if p.strip()]

    # Separado por espacios sueltos. Las cifras son la cola del renglon, asi
    # que se corta ahi: partir por los ultimos espacios rompia los nombres
    # largos ("Efectivo y equivalentes 450 380" perdia "equivalentes").
    cola = re.search(r"^(.*?)((?:\s+\(?-?[\d.,]+\)?%?)+)$", texto)
    if not cola:
        return [texto]
    etiqueta = cola.group(1).strip()
    cifras = cola.group(2).split()
    return ([etiqueta] if etiqueta else []) + cifras


EXTENSIONES = {
    ".xlsx": leer_excel, ".xlsm": leer_excel,
    ".csv": leer_csv, ".txt": leer_csv,
    ".pdf": leer_pdf,
}


def importar(nombre: str, contenido: bytes) -> Tabla:
    """Lee un archivo y devuelve la tabla con el mapeo ya propuesto.

    No calcula ni valida nada financiero: eso es del motor, y solo despues de
    que el usuario confirme el mapeo en pantalla.
    """
    extension = "." + nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
    lector = EXTENSIONES.get(extension)
    if lector is None:
        raise ValueError(
            f"Formato no soportado ({extension or 'sin extension'}). "
            "Se aceptan Excel (.xlsx), CSV (.csv) y PDF (.pdf).")
    if not contenido:
        raise ValueError("El archivo llego vacio.")

    tabla = Tabla(origen=nombre)
    lector(contenido, tabla)

    if not tabla.filas:
        raise ValueError(
            "No se encontro ninguna fila con cifras. Revise que el archivo tenga "
            "una columna con los nombres de las cuentas y al menos una con numeros.")

    if not tabla.periodos:
        columnas = max(len(f.valores) for f in tabla.filas)
        tabla.periodos = [f"Periodo {i + 1}" for i in range(columnas)]
        tabla.avisos.append(
            "No se reconocieron los anos en los encabezados, asi que las columnas "
            "quedaron como Periodo 1, 2... Renombrelas antes de analizar.")

    mapear(tabla)

    sin_asignar = [f for f in tabla.filas if not f.cuenta]
    if sin_asignar:
        tabla.avisos.append(
            f"{len(sin_asignar)} de {len(tabla.filas)} filas no se reconocieron con "
            "el diccionario. Puede asignarlas a mano o pedirle una propuesta al "
            "modelo, que igual tendra que confirmar.")
    return tabla


# ------------------------------------------------------- armado del resultado


def armar_estados(tabla_cruda: dict, empresa: str = "", moneda: str = "COP",
                  unidad: str = "millones") -> dict:
    """Convierte la tabla ya confirmada en el JSON que come el motor.

    Recibe el mapeo tal como quedo en pantalla, con las correcciones del
    usuario. Las cuentas que nadie asigno simplemente no van: el motor sabe
    trabajar con cuentas ausentes y reportarlas como no disponibles.
    """
    periodos = [str(p) for p in tabla_cruda.get("periodos") or []]
    if not periodos:
        raise ValueError("La tabla no tiene periodos.")

    datos = {
        "empresa": empresa or tabla_cruda.get("empresa") or "Empresa importada",
        "moneda": moneda,
        "unidad": unidad,
        "periodos": periodos,
        "balance": {},
        "resultados": {},
    }

    usadas = set()
    for fila in tabla_cruda.get("filas") or []:
        cuenta = fila.get("cuenta")
        if not cuenta or cuenta not in GRUPO or cuenta in usadas:
            continue
        valores = [leer_numero(v) for v in (fila.get("valores") or [])]
        # Todas las cuentas tienen que traer un valor por periodo: si sobran se
        # recortan y si faltan se completan con None, nunca con cero.
        valores = (valores + [None] * len(periodos))[:len(periodos)]
        if all(v is None for v in valores):
            continue
        datos[GRUPO[cuenta]][cuenta] = valores
        usadas.add(cuenta)

    if not datos["balance"] and not datos["resultados"]:
        raise ValueError(
            "Ninguna fila quedo asignada a una cuenta conocida. Asigne al menos "
            "las cuentas principales antes de analizar.")
    return datos
