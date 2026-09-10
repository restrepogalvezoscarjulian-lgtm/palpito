"""Validación de calidad de los datos ANTES de calcular indicadores.

Regla de oro del proyecto: si los estados financieros no son consistentes,
cualquier indicador que se calcule sobre ellos es un número bonito y falso.
Este modulo se ejecuta primero y siempre.
"""

from __future__ import annotations

from .modelos import EstadosFinancieros, Hallazgo

TOLERANCIA = 0.01  # margen por redondeo, en unidades del caso


def _cerca(a: float, b: float) -> bool:
    return abs(a - b) <= TOLERANCIA


def validar(ef: EstadosFinancieros) -> list[Hallazgo]:
    """Corre todas las verificaciones y devuelve los hallazgos encontrados."""
    hallazgos: list[Hallazgo] = []
    for i, periodo in enumerate(ef.periodos):
        hallazgos += _ecuacion_contable(ef, i, periodo)
        hallazgos += _subtotales_balance(ef, i, periodo)
        hallazgos += _encadenamiento_resultados(ef, i, periodo)
        hallazgos += _valores_imposibles(ef, i, periodo)
    hallazgos += _catalogo_no_encaja(ef)
    hallazgos += _datos_faltantes(ef)
    return hallazgos


# ------------------------------------------------------------------ chequeos


def _ecuacion_contable(ef: EstadosFinancieros, i: int, periodo: str) -> list[Hallazgo]:
    """Activo = Pasivo + Patrimonio. La verificacion más importante de todas."""
    activo = ef.valor("activo_total", i)
    pasivo = ef.pasivo_total(i)
    patrimonio = ef.valor("patrimonio", i)
    if activo is None or pasivo is None or patrimonio is None:
        return []
    diferencia = activo - (pasivo + patrimonio)
    if _cerca(diferencia, 0):
        return []
    return [
        Hallazgo(
            severidad="error",
            codigo="ECUACION_CONTABLE",
            mensaje=(
                f"{periodo}: el balance no cuadra por {diferencia:,.0f} "
                f"{ef.moneda} ({ef.unidad})."
            ),
            detalle=(
                f"Activo total {activo:,.0f} != Pasivo {pasivo:,.0f} + "
                f"Patrimonio {patrimonio:,.0f} = {pasivo + patrimonio:,.0f}. "
                "Faltan cuentas de pasivo en la información entregada, o hay un "
                "error de digitación. Los indicadores de endeudamiento calculados "
                "sobre estos datos quedan subestimados."
            ),
        )
    ]


def _subtotales_balance(ef: EstadosFinancieros, i: int, periodo: str) -> list[Hallazgo]:
    """Los subtotales declarados deben cuadrar con las partidas listadas."""
    salida: list[Hallazgo] = []

    grupos = [
        ("activo_corriente", ["efectivo", "cuentas_por_cobrar", "inventarios"], "activo corriente"),
        ("pasivo_corriente", ["proveedores", "deuda_financiera_cp"], "pasivo corriente"),
    ]
    for subtotal, partidas, etiqueta in grupos:
        declarado = ef.valor(subtotal, i)
        if declarado is None:
            continue
        presentes = [ef.valor(p, i) for p in partidas]
        if any(v is None for v in presentes):
            continue
        suma = sum(presentes)
        if _cerca(suma, declarado):
            continue
        brecha = declarado - suma
        if brecha > 0:
            severidad = "advertencia"
            mensaje = (
                f"{periodo}: el {etiqueta} declarado ({declarado:,.0f}) supera la suma "
                f"de las partidas listadas ({suma:,.0f}) en {brecha:,.0f}."
            )
            detalle = (
                "Existen partidas no informadas dentro del subtotal. No es "
                "necesariamente un error, pero limita el detalle del análisis."
            )
        else:
            severidad = "error"
            mensaje = (
                f"{periodo}: las partidas de {etiqueta} suman {suma:,.0f}, más que el "
                f"subtotal declarado ({declarado:,.0f})."
            )
            detalle = "Esto si es inconsistente: revisar digitación."
        salida.append(
            Hallazgo(severidad=severidad, codigo="SUBTOTAL_BALANCE", mensaje=mensaje, detalle=detalle)
        )

    # Activo total = activo corriente + activo no corriente
    total = ef.valor("activo_total", i)
    corriente = ef.valor("activo_corriente", i)
    ppe = ef.valor("propiedad_planta_equipo", i)
    if None not in (total, corriente, ppe) and not _cerca(corriente + ppe, total):
        salida.append(
            Hallazgo(
                severidad="error",
                codigo="SUBTOTAL_ACTIVO",
                mensaje=(
                    f"{periodo}: activo corriente + PPE ({corriente + ppe:,.0f}) no coincide "
                    f"con el activo total declarado ({total:,.0f})."
                ),
            )
        )
    return salida


def _encadenamiento_resultados(ef: EstadosFinancieros, i: int, periodo: str) -> list[Hallazgo]:
    """Cada renglon del estado de resultados debe derivarse del anterior."""
    salida: list[Hallazgo] = []
    cadena = [
        ("utilidad_bruta", ["ventas"], ["costo_ventas"], "Utilidad bruta"),
        ("utilidad_operacional", ["utilidad_bruta"], ["gastos_operacionales"], "Utilidad operacional"),
        ("utilidad_antes_impuestos", ["utilidad_operacional"], ["gastos_financieros"], "Utilidad antes de impuestos"),
        ("utilidad_neta", ["utilidad_antes_impuestos"], ["impuestos"], "Utilidad neta"),
    ]
    for resultado, suman, restan, etiqueta in cadena:
        declarado = ef.valor(resultado, i)
        piezas = [ef.valor(c, i) for c in suman + restan]
        if declarado is None or any(v is None for v in piezas):
            continue
        calculado = sum(ef.valor(c, i) for c in suman) - sum(ef.valor(c, i) for c in restan)
        if not _cerca(calculado, declarado):
            salida.append(
                Hallazgo(
                    severidad="error",
                    codigo="CADENA_RESULTADOS",
                    mensaje=(
                        f"{periodo}: {etiqueta} declarada {declarado:,.0f} pero el "
                        f"encadenamiento da {calculado:,.0f}."
                    ),
                )
            )
    return salida


def _valores_imposibles(ef: EstadosFinancieros, i: int, periodo: str) -> list[Hallazgo]:
    """Cuentas que por su naturaleza no pueden ser negativas."""
    no_negativas = [
        "efectivo", "cuentas_por_cobrar", "inventarios", "activo_corriente",
        "activo_total", "proveedores", "pasivo_corriente", "ventas", "costo_ventas",
    ]
    salida = []
    for nombre in no_negativas:
        v = ef.valor(nombre, i)
        if v is not None and v < 0:
            salida.append(
                Hallazgo(
                    severidad="error",
                    codigo="VALOR_NEGATIVO",
                    mensaje=f"{periodo}: la cuenta {nombre} es negativa ({v:,.0f}).",
                )
            )
    return salida


def _catalogo_no_encaja(ef: EstadosFinancieros) -> list[Hallazgo]:
    """Detecta que estos estados no son de una empresa que el catalogo cubra.

    Palpito conoce 23 cuentas pensadas para una empresa que COMPRA, GUARDA y
    VENDE. Un banco o una aseguradora no hacen eso: sus ingresos son intereses,
    su "costo" es lo que le paga a los ahorradores, y su balance no se parte en
    corriente y no corriente.

    El 10-sep-2026 se cargo el consolidado de Grupo Bolivar -dueno de
    Davivienda- y salio semaforo VERDE. Reconocio 13 cuentas y ninguna
    verificacion se quejo, porque las que podrian haberlo hecho necesitan
    cuentas que un banco no reporta: sin pasivo corriente no hay ecuacion
    contable que cuadrar, y sin subtotales no hay subtotales que revisar. El
    resultado fue un analisis sin sentido con luz verde, que es peor que uno
    con luz roja: el rojo se discute, el verde se cree.

    Las senales de abajo no dicen "la empresa esta mal". Dicen "esta vara no
    mide esta empresa".
    """
    salida: list[Hallazgo] = []
    consejo = (
        "Palpito esta hecho para una empresa que compra, guarda y vende. En un "
        "banco, una aseguradora o un holding, los indicadores se calculan igual "
        "pero no significan lo mismo. Use los estados de una empresa operativa, "
        "o interprete estas cifras con esa advertencia por delante."
    )

    for i, periodo in enumerate(ef.periodos):
        ventas = ef.valor("ventas", i)
        if ventas is None or ventas <= 0:
            continue
        costo = ef.valor("costo_ventas", i)
        if costo is not None and costo > ventas:
            salida.append(Hallazgo(
                severidad="error",
                codigo="CATALOGO_NO_ENCAJA",
                mensaje=(f"{periodo}: el costo de ventas ({costo:,.0f}) supera a las "
                         f"ventas ({ventas:,.0f})."),
                detalle=("Vender por debajo del costo un ano entero es raro; lo "
                         "corriente es que esas dos etiquetas no sean lo que el "
                         "motor cree. " + consejo),
            ))
        financieros = ef.valor("gastos_financieros", i)
        if financieros is not None and financieros > ventas:
            salida.append(Hallazgo(
                severidad="error",
                codigo="CATALOGO_NO_ENCAJA",
                mensaje=(f"{periodo}: los gastos financieros ({financieros:,.0f}) "
                         f"superan a las ventas ({ventas:,.0f})."),
                detalle=("Una empresa no puede pagar mas intereses de lo que vende. "
                         "En un banco si: los intereses que paga son su costo de "
                         "operar, no una carga de deuda. " + consejo),
            ))

    # Un balance sin la division corriente / no corriente no es de una empresa
    # comercial. Sin esas cuentas, media validacion se queda sin nada que mirar.
    if ef.existe("activo_total") and not ef.existe("activo_corriente") \
            and not ef.existe("pasivo_corriente"):
        salida.append(Hallazgo(
            severidad="error",
            codigo="CATALOGO_NO_ENCAJA",
            mensaje="El balance no separa lo corriente de lo no corriente.",
            detalle=("Asi presentan sus estados los bancos y las aseguradoras. Sin "
                     "esa division no hay liquidez que medir, y la ecuacion "
                     "contable no se puede verificar. " + consejo),
        ))
    return salida


def _datos_faltantes(ef: EstadosFinancieros) -> list[Hallazgo]:
    """Avisa que indicadores NO se van a poder calcular, y por que."""
    requisitos = {
        "depreciacion": ["EBITDA", "Flujo de Caja Bruto", "Flujo de Caja Libre"],
        "compras": ["Rotación de proveedores exacta (se usa costo de ventas como aproximación)"],
        "ventas_credito": ["Rotación de cartera exacta (se usan las ventas totales)"],
    }
    salida = []
    for cuenta, afectados in requisitos.items():
        if not ef.existe(cuenta):
            salida.append(
                Hallazgo(
                    severidad="info",
                    codigo="DATO_FALTANTE",
                    mensaje=f"No se informo la cuenta: {cuenta}.",
                    detalle="Afecta a: " + "; ".join(afectados) + ".",
                )
            )
    return salida


# ------------------------------------------------------------------- resumen


def semaforo(hallazgos: list[Hallazgo]) -> str:
    """Estado global de la calidad de los datos."""
    if any(h.severidad == "error" for h in hallazgos):
        return "rojo"
    if any(h.severidad == "advertencia" for h in hallazgos):
        return "amarillo"
    return "verde"


def resumen(hallazgos: list[Hallazgo]) -> dict:
    return {
        "semaforo": semaforo(hallazgos),
        "errores": sum(1 for h in hallazgos if h.severidad == "error"),
        "advertencias": sum(1 for h in hallazgos if h.severidad == "advertencia"),
        "informativos": sum(1 for h in hallazgos if h.severidad == "info"),
    }
