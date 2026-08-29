"""Validacion de calidad de los datos ANTES de calcular indicadores.

Regla de oro del proyecto: si los estados financieros no son consistentes,
cualquier indicador que se calcule sobre ellos es un numero bonito y falso.
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
    hallazgos += _datos_faltantes(ef)
    return hallazgos


# ------------------------------------------------------------------ chequeos


def _ecuacion_contable(ef: EstadosFinancieros, i: int, periodo: str) -> list[Hallazgo]:
    """Activo = Pasivo + Patrimonio. La verificacion mas importante de todas."""
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
                "Faltan cuentas de pasivo en la informacion entregada, o hay un "
                "error de digitacion. Los indicadores de endeudamiento calculados "
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
                "necesariamente un error, pero limita el detalle del analisis."
            )
        else:
            severidad = "error"
            mensaje = (
                f"{periodo}: las partidas de {etiqueta} suman {suma:,.0f}, mas que el "
                f"subtotal declarado ({declarado:,.0f})."
            )
            detalle = "Esto si es inconsistente: revisar digitacion."
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


def _datos_faltantes(ef: EstadosFinancieros) -> list[Hallazgo]:
    """Avisa que indicadores NO se van a poder calcular, y por que."""
    requisitos = {
        "depreciacion": ["EBITDA", "Flujo de Caja Bruto", "Flujo de Caja Libre"],
        "compras": ["Rotacion de proveedores exacta (se usa costo de ventas como aproximacion)"],
        "ventas_credito": ["Rotacion de cartera exacta (se usan las ventas totales)"],
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
