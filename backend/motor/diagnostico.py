"""Motor de reglas: convierte indicadores en alertas priorizadas.

Este modulo NO usa inteligencia artificial. Son reglas explicitas y auditables.
La IA (modulo narrativa) solo redacta en lenguaje natural lo que aqui se decide,
y siempre citando la evidencia numerica que estas reglas producen.

Responde al paso 5 del taller: explicar las causas del deterioro y senalar las
cuentas responsables.
"""

from __future__ import annotations

from .indicadores import analisis_horizontal, calcular_todos, dupont, puente_caja
from .modelos import Alerta, EstadosFinancieros


def _fmt(v, unidad="", dec=2):
    if v is None:
        return "n/d"
    txt = f"{v:,.{dec}f}"
    return f"{txt}{unidad}"


def diagnosticar(ef: EstadosFinancieros) -> list[Alerta]:
    """Evalua todas las reglas y devuelve las alertas ordenadas por prioridad."""
    ind = calcular_todos(ef)
    hor = analisis_horizontal(ef)
    alertas: list[Alerta] = []

    for regla in (
        _regla_costos_crecen_mas_que_ventas,
        _regla_cartera_crece_mas_que_ventas,
        _regla_inventario_crece_mas_que_ventas,
        _regla_ciclo_caja_se_alarga,
        _regla_gastos_financieros,
        _regla_cobertura_intereses,
        _regla_calidad_liquidez,
        _regla_flujo_caja_negativo,
        _regla_roic_vs_costo_deuda,
        _regla_dupont,
        _regla_endeudamiento_creciente,
    ):
        resultado = regla(ef, ind, hor)
        if resultado:
            alertas.append(resultado)

    alertas.sort(key=lambda a: a.prioridad)
    for n, a in enumerate(alertas, start=1):
        a.prioridad = n
    return alertas


# ------------------------------------------------------------------- reglas


def _regla_costos_crecen_mas_que_ventas(ef, ind, hor) -> Alerta | None:
    v = hor["resultados"].get("ventas", {}).get("variacion_relativa")
    c = hor["resultados"].get("costo_ventas", {}).get("variacion_relativa")
    if None in (v, c) or c <= v:
        return None
    return Alerta(
        prioridad=1,
        titulo="El costo de ventas crece mas rapido que las ventas",
        explicacion=(
            "Cada peso adicional vendido esta dejando menos margen que antes. "
            "Puede ser alza de proveedores, descuentos comerciales para sostener "
            "el volumen, o cambio en la mezcla de productos hacia referencias menos rentables."
        ),
        evidencia=[
            f"Ventas: {_fmt(v)}%",
            f"Costo de ventas: {_fmt(c)}%",
            f"Margen bruto: {_fmt(ind['margen_bruto'].valores[0])}% -> {_fmt(ind['margen_bruto'].valores[-1])}%",
        ],
        cuentas=["ventas", "costo_ventas"],
    )


def _regla_cartera_crece_mas_que_ventas(ef, ind, hor) -> Alerta | None:
    v = hor["resultados"].get("ventas", {}).get("variacion_relativa")
    c = hor["balance"].get("cuentas_por_cobrar", {}).get("variacion_relativa")
    if None in (v, c) or c <= v:
        return None
    dias = ind["dias_cartera"].valores
    return Alerta(
        prioridad=2,
        titulo="La cartera crece mas rapido que las ventas",
        explicacion=(
            "Se esta vendiendo, pero el dinero se queda en manos de los clientes. "
            "O se alargaron los plazos para poder vender, o la cobranza se relajo."
        ),
        evidencia=[
            f"Cuentas por cobrar: {_fmt(c)}% vs ventas {_fmt(v)}%",
            f"Dias de cartera: {_fmt(dias[0], ' dias', 1)} -> {_fmt(dias[-1], ' dias', 1)}",
        ],
        cuentas=["cuentas_por_cobrar", "ventas"],
    )


def _regla_inventario_crece_mas_que_ventas(ef, ind, hor) -> Alerta | None:
    v = hor["resultados"].get("ventas", {}).get("variacion_relativa")
    inv = hor["balance"].get("inventarios", {}).get("variacion_relativa")
    if None in (v, inv) or inv <= v:
        return None
    dias = ind["dias_inventario"].valores
    return Alerta(
        prioridad=3,
        titulo="El inventario crece mas rapido que las ventas",
        explicacion=(
            "Hay mas mercancia parada en bodega por cada peso que se vende. "
            "Suele indicar referencias de baja rotacion o compras por encima de la demanda real."
        ),
        evidencia=[
            f"Inventarios: {_fmt(inv)}% vs ventas {_fmt(v)}%",
            f"Dias de inventario: {_fmt(dias[0], ' dias', 1)} -> {_fmt(dias[-1], ' dias', 1)}",
        ],
        cuentas=["inventarios", "ventas"],
    )


def _regla_ciclo_caja_se_alarga(ef, ind, hor) -> Alerta | None:
    c = ind["ciclo_conversion_efectivo"].valores
    if c[0] is None or c[-1] is None or c[-1] <= c[0]:
        return None
    dp = ind["dias_proveedores"].valores
    ev = [f"Ciclo de caja: {_fmt(c[0], ' dias', 1)} -> {_fmt(c[-1], ' dias', 1)} (+{c[-1]-c[0]:,.1f})"]
    if dp[0] is not None and dp[-1] is not None and dp[-1] < dp[0]:
        ev.append(f"Ademas se le paga MAS RAPIDO a proveedores: {_fmt(dp[0], ' dias', 1)} -> {_fmt(dp[-1], ' dias', 1)}")
    return Alerta(
        prioridad=2,
        titulo="El ciclo de conversion de efectivo se alargo",
        explicacion=(
            "La plata pasa mas dias fuera de la caja. Cada dia adicional del ciclo "
            "obliga a financiar mas capital de trabajo, con deuda o con recursos propios."
        ),
        evidencia=ev,
        cuentas=["cuentas_por_cobrar", "inventarios", "proveedores"],
    )


def _regla_gastos_financieros(ef, ind, hor) -> Alerta | None:
    g = hor["resultados"].get("gastos_financieros", {}).get("variacion_relativa")
    v = hor["resultados"].get("ventas", {}).get("variacion_relativa")
    if g is None or g <= 20:
        return None
    return Alerta(
        prioridad=2,
        titulo="Los gastos financieros se dispararon",
        explicacion=(
            "El costo de la deuda esta absorbiendo la utilidad operativa. "
            "Es el efecto, no la causa: la empresa se endeudo para financiar algo."
        ),
        evidencia=[
            f"Gastos financieros: {_fmt(g)}%" + (f" (ventas solo {_fmt(v)}%)" if v is not None else ""),
            f"Costo implicito de la deuda: {_fmt(ind['costo_deuda_implicito'].valores[-1])}%",
        ],
        cuentas=["gastos_financieros", "deuda_financiera_cp", "deuda_financiera_lp"],
    )


def _regla_cobertura_intereses(ef, ind, hor) -> Alerta | None:
    c = ind["cobertura_intereses"].valores
    if c[-1] is None:
        return None
    if c[-1] >= 5 and (c[0] is None or c[-1] >= c[0]):
        return None
    critica = c[-1] < 2
    return Alerta(
        prioridad=1 if critica else 3,
        titulo=("Cobertura de intereses en zona critica" if critica
                else "La cobertura de intereses se deterioro"),
        explicacion=(
            "Mide cuantas veces la operacion alcanza a pagar los intereses. "
            "Por debajo de 2 veces, cualquier tropiezo operativo compromete el pago de la deuda."
        ),
        evidencia=[f"Cobertura: {_fmt(c[0], ' veces')} -> {_fmt(c[-1], ' veces')}"],
        cuentas=["utilidad_operacional", "gastos_financieros"],
    )


def _regla_calidad_liquidez(ef, ind, hor) -> Alerta | None:
    rc, re = ind["razon_corriente"].valores, ind["razon_efectivo"].valores
    if None in (rc[0], rc[-1], re[0], re[-1]):
        return None
    estable = abs(rc[-1] - rc[0]) < 0.10
    efectivo_cae = re[-1] < re[0] * 0.8
    if not (estable and efectivo_cae):
        return None
    return Alerta(
        prioridad=2,
        titulo="La liquidez parece estable pero su calidad se deterioro",
        explicacion=(
            "La razon corriente casi no se movio, asi que a primera vista todo esta bien. "
            "Pero el activo corriente crecio a punta de cartera e inventario (lo lento) "
            "mientras el efectivo (lo liquido) se redujo. Es una senal que se pierde si "
            "solo se mira la razon corriente."
        ),
        evidencia=[
            f"Razon corriente: {_fmt(rc[0])} -> {_fmt(rc[-1])} (casi sin cambio)",
            f"Prueba acida: {_fmt(ind['prueba_acida'].valores[0])} -> {_fmt(ind['prueba_acida'].valores[-1])}",
            f"Razon de efectivo: {_fmt(re[0])} -> {_fmt(re[-1])}",
        ],
        cuentas=["efectivo", "cuentas_por_cobrar", "inventarios"],
    )


def _regla_flujo_caja_negativo(ef, ind, hor) -> Alerta | None:
    p = puente_caja(ef)
    if not p.get("disponible") or p.get("flujo_caja_libre_aprox") is None:
        return None
    if p["flujo_caja_libre_aprox"] >= 0:
        return None
    u, k, a = p["uodi"], p["aumento_ktno"], p["aumento_activos_fijos_neto"]
    return Alerta(
        prioridad=1,
        titulo="La operacion no genero caja suficiente para financiarse sola",
        explicacion=(
            "Esta es la respuesta a 'vendi mas pero tengo menos plata'. La utilidad "
            "operativa despues de impuestos no alcanzo a cubrir lo que se tragaron el "
            "capital de trabajo y la inversion en activos fijos. La diferencia se cubrio "
            "con deuda y con el efectivo que habia en caja."
        ),
        evidencia=[
            f"UODI generada: {_fmt(u, '', 0)}",
            f"Consumido por aumento del KTNO: -{_fmt(k, '', 0)}",
            f"Consumido por activos fijos: -{_fmt(a, '', 0)}",
            f"Flujo de caja libre aproximado: {_fmt(p['flujo_caja_libre_aprox'], '', 0)}",
            f"Deuda financiera: +{_fmt(p['variacion_deuda_financiera'], '', 0)}",
            f"Efectivo: {_fmt(p['variacion_efectivo'], '', 0)}",
        ],
        cuentas=["cuentas_por_cobrar", "inventarios", "proveedores",
                 "propiedad_planta_equipo", "deuda_financiera_cp", "deuda_financiera_lp"],
    )


def _regla_roic_vs_costo_deuda(ef, ind, hor) -> Alerta | None:
    roic = ind["roic"].valores[-1]
    kd = ind["costo_deuda_implicito"].valores[-1]
    if None in (roic, kd) or roic - kd > 3:
        return None
    return Alerta(
        prioridad=1,
        titulo="El negocio rinde casi lo mismo que cuesta la deuda",
        explicacion=(
            "El capital invertido rinde apenas por encima (o por debajo) de lo que se "
            "paga por la plata prestada. En esa franja, crecer con deuda no agrega valor: "
            "lo destruye. Es la logica del EVA."
        ),
        evidencia=[
            f"ROIC: {_fmt(roic)}%",
            f"Costo implicito de la deuda: {_fmt(kd)}%",
            f"Diferencia: {_fmt(roic - kd)} puntos",
        ],
        cuentas=["utilidad_operacional", "deuda_financiera_cp", "deuda_financiera_lp"],
    )


def _regla_dupont(ef, ind, hor) -> Alerta | None:
    d = dupont(ef)
    var = d.get("variacion_por_factor_pct")
    roe = ind["roe"].valores
    if not var or None in (roe[0], roe[-1]) or roe[-1] >= roe[0]:
        return None
    culpable = min(var, key=lambda k: var[k] if var[k] is not None else 0)
    nombres = {
        "margen_neto": "el MARGEN (rentabilidad por peso vendido)",
        "rotacion_activos": "la ROTACION (eficiencia de los activos)",
        "multiplicador_patrimonio": "el APALANCAMIENTO (estructura de financiacion)",
    }
    return Alerta(
        prioridad=2,
        titulo=f"La caida del ROE se explica por {nombres[culpable]}",
        explicacion=(
            "El sistema DuPont separa la rentabilidad del socio en tres palancas. "
            "Identificar cual se movio dice donde hay que actuar: margen es un problema "
            "de precios y costos; rotacion, de eficiencia en activos; apalancamiento, "
            "de estructura de deuda."
        ),
        evidencia=[
            f"ROE: {_fmt(roe[0])}% -> {_fmt(roe[-1])}%",
            f"Margen neto: {_fmt(var['margen_neto'])}%",
            f"Rotacion de activos: {_fmt(var['rotacion_activos'])}%",
            f"Multiplicador del patrimonio: {_fmt(var['multiplicador_patrimonio'])}%",
        ],
        cuentas=["utilidad_neta", "ventas", "activo_total", "patrimonio"],
    )


def _regla_endeudamiento_creciente(ef, ind, hor) -> Alerta | None:
    e = ind["endeudamiento_activo"].valores
    if None in (e[0], e[-1]) or e[-1] - e[0] < 3:
        return None
    imp = ind["endeudamiento_activo_implicito"].valores
    ev = [f"Endeudamiento: {_fmt(e[0])}% -> {_fmt(e[-1])}%"]
    if imp[-1] is not None and abs(imp[-1] - e[-1]) > 1:
        ev.append(
            f"ATENCION: con el balance cuadrado el endeudamiento real seria "
            f"{_fmt(imp[-1])}%, no {_fmt(e[-1])}%. Hay pasivos no informados."
        )
    return Alerta(
        prioridad=3,
        titulo="El nivel de endeudamiento aumento",
        explicacion="Mayor dependencia de terceros y menor margen de maniobra para nueva deuda.",
        evidencia=ev,
        cuentas=["pasivo_corriente", "deuda_financiera_lp", "activo_total"],
    )


# ------------------------------------------------------------- recomendaciones

RECOMENDACIONES = {
    "cuentas_por_cobrar": (
        "Cartera: revisar politica de plazos y reforzar cobranza. Cada dia menos de "
        "cartera libera caja sin necesidad de vender mas."
    ),
    "inventarios": (
        "Inventarios: identificar referencias de baja rotacion y liquidarlas. "
        "Ajustar las compras a la demanda real, no al descuento por volumen."
    ),
    "costo_ventas": (
        "Costos: renegociar con proveedores y revisar la mezcla de productos. "
        "Priorizar las referencias de mayor margen de contribucion."
    ),
    "gastos_financieros": (
        "Deuda: refinanciar las obligaciones mas costosas y alargar plazos para "
        "aliviar la presion sobre la caja."
    ),
    "propiedad_planta_equipo": (
        "Inversion: aplazar CAPEX no critico hasta que la operacion vuelva a generar "
        "caja propia."
    ),
    "gastos_operacionales": (
        "Gastos de administracion y ventas: revisar los que crecieron por encima de las ventas."
    ),
}


def recomendaciones(alertas: list[Alerta], maximo: int = 3) -> list[str]:
    """Deriva recomendaciones accionables de las alertas, sin repetir tema."""
    salida, vistas = [], set()
    for a in alertas:
        for cuenta in a.cuentas:
            if cuenta in RECOMENDACIONES and cuenta not in vistas:
                vistas.add(cuenta)
                salida.append(RECOMENDACIONES[cuenta])
                if len(salida) >= maximo:
                    return salida
    return salida
