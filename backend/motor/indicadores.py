"""Calculo de indicadores financieros.

Todo lo que hay aqui es deterministico: mismas entradas, mismas salidas,
sin intervencion de ningun modelo de lenguaje. Cada indicador viaja con su
formula y sus insumos para que cualquiera pueda auditar de donde salio.

Criterios adoptados y fuentes en FORMULAS.md.
"""

from __future__ import annotations

from .modelos import EstadosFinancieros, Indicador

# Fuentes bibliograficas citadas por los indicadores
BAENA = "Baena Toro, D. (2014). Analisis financiero: enfoque y proyecciones"
GARCIA = "Garcia S., O. L. Administracion financiera: fundamentos y aplicaciones"
CARTILLA = "Barbosa Guerrero, L. M. (2021). Analisis y gerencia financiera, U. El Bosque"


def _div(numerador, denominador):
    """Division tolerante: devuelve None si falta un dato o el divisor es cero."""
    if numerador is None or denominador is None or denominador == 0:
        return None
    return numerador / denominador


def _serie(ef: EstadosFinancieros, fn):
    """Aplica fn(i) a cada periodo y devuelve la lista de resultados."""
    return [fn(i) for i in range(ef.n_periodos)]


# ============================================================ ANALISIS VERTICAL


def analisis_vertical(ef: EstadosFinancieros) -> dict:
    """Peso de cada cuenta sobre el total de su grupo, en porcentaje."""
    bases = {
        "balance": "activo_total",
        "resultados": "ventas",
    }
    salida = {}
    for grupo, base in bases.items():
        cuentas = ef.balance if grupo == "balance" else ef.resultados
        filas = {}
        for nombre in cuentas:
            filas[nombre] = [
                _div(ef.valor(nombre, i), ef.valor(base, i)) and
                _div(ef.valor(nombre, i), ef.valor(base, i)) * 100
                for i in range(ef.n_periodos)
            ]
        salida[grupo] = {"base": base, "filas": filas}
    return salida


# ========================================================== ANALISIS HORIZONTAL


def analisis_horizontal(ef: EstadosFinancieros) -> dict:
    """Variacion absoluta y relativa entre el primer y el ultimo periodo."""
    salida = {}
    for grupo, cuentas in (("balance", ef.balance), ("resultados", ef.resultados)):
        filas = {}
        for nombre in cuentas:
            serie = ef.cuenta(nombre)
            ini, fin = serie[0], serie[-1]
            absoluta = None if (ini is None or fin is None) else fin - ini
            relativa = None
            if ini not in (None, 0) and fin is not None:
                relativa = (fin / ini - 1) * 100
            filas[nombre] = {
                "inicial": ini,
                "final": fin,
                "variacion_absoluta": absoluta,
                "variacion_relativa": relativa,
            }
        salida[grupo] = filas
    return salida


# ==================================================================== LIQUIDEZ


def _liquidez(ef: EstadosFinancieros) -> list[Indicador]:
    return [
        Indicador(
            codigo="razon_corriente",
            nombre="Razon corriente",
            categoria="Liquidez",
            valores=_serie(ef, lambda i: _div(ef.valor("activo_corriente", i), ef.valor("pasivo_corriente", i))),
            unidad="veces",
            formula="Activo corriente / Pasivo corriente",
            insumos=["activo_corriente", "pasivo_corriente"],
            fuente=CARTILLA,
            nota="Mayor a 1 sugiere capacidad de cubrir obligaciones de corto plazo. "
                 "Ojo: no dice nada sobre la CALIDAD del activo corriente.",
        ),
        Indicador(
            codigo="prueba_acida",
            nombre="Prueba acida",
            categoria="Liquidez",
            valores=_serie(ef, lambda i: _div(
                None if None in (ef.valor("activo_corriente", i), ef.valor("inventarios", i))
                else ef.valor("activo_corriente", i) - ef.valor("inventarios", i),
                ef.valor("pasivo_corriente", i))),
            unidad="veces",
            formula="(Activo corriente - Inventarios) / Pasivo corriente",
            insumos=["activo_corriente", "inventarios", "pasivo_corriente"],
            fuente=BAENA,
            nota="Quita el inventario, que es el activo corriente mas lento de volverse caja.",
        ),
        Indicador(
            codigo="razon_efectivo",
            nombre="Razon de efectivo",
            categoria="Liquidez",
            valores=_serie(ef, lambda i: _div(ef.valor("efectivo", i), ef.valor("pasivo_corriente", i))),
            unidad="veces",
            formula="Efectivo / Pasivo corriente",
            insumos=["efectivo", "pasivo_corriente"],
            fuente=BAENA,
            nota="La prueba mas exigente: solo cuenta la plata que ya esta en el banco.",
        ),
        Indicador(
            codigo="capital_trabajo_neto",
            nombre="Capital de trabajo neto contable",
            categoria="Liquidez",
            valores=_serie(ef, lambda i:
                None if None in (ef.valor("activo_corriente", i), ef.valor("pasivo_corriente", i))
                else ef.valor("activo_corriente", i) - ef.valor("pasivo_corriente", i)),
            unidad="monto",
            formula="Activo corriente - Pasivo corriente",
            insumos=["activo_corriente", "pasivo_corriente"],
            fuente=GARCIA,
            nota="Garcia advierte que esta definicion contable es limitada. "
                 "El KTNO es la medida operativa correcta.",
        ),
    ]


# =================================================================== ACTIVIDAD


def _actividad(ef: EstadosFinancieros) -> list[Indicador]:
    dias = ef.supuestos.get("dias_anio", 365)
    usa_proxy_cartera = not ef.existe("ventas_credito")
    usa_proxy_compras = not ef.existe("compras")
    base_cartera = "ventas" if usa_proxy_cartera else "ventas_credito"
    base_compras = "costo_ventas" if usa_proxy_compras else "compras"

    def rot(base, cuenta, i):
        return _div(ef.valor(base, i), ef.valor(cuenta, i))

    def dias_de(base, cuenta, i):
        r = rot(base, cuenta, i)
        return None if r in (None, 0) else dias / r

    def ktno(i):
        piezas = [ef.valor("cuentas_por_cobrar", i), ef.valor("inventarios", i), ef.valor("proveedores", i)]
        if any(p is None for p in piezas):
            return None
        return piezas[0] + piezas[1] - piezas[2]

    def ciclo(i):
        partes = [
            dias_de(base_cartera, "cuentas_por_cobrar", i),
            dias_de(base_compras, "inventarios", i),
            dias_de(base_compras, "proveedores", i),
        ]
        if any(p is None for p in partes):
            return None
        return partes[0] + partes[1] - partes[2]

    proxy_cartera = " (se usan ventas totales: el caso no separa ventas a credito)" if usa_proxy_cartera else ""
    proxy_compras = " (se usa costo de ventas como aproximacion de compras)" if usa_proxy_compras else ""

    return [
        Indicador(
            codigo="dias_cartera",
            nombre="Dias de cartera",
            categoria="Actividad",
            valores=_serie(ef, lambda i: dias_de(base_cartera, "cuentas_por_cobrar", i)),
            unidad="dias",
            formula=f"{dias} / (Ventas a credito / Cuentas por cobrar)",
            insumos=[base_cartera, "cuentas_por_cobrar"],
            fuente=CARTILLA,
            nota="Cuanto se demora en promedio en cobrar." + proxy_cartera,
        ),
        Indicador(
            codigo="dias_inventario",
            nombre="Dias de inventario",
            categoria="Actividad",
            valores=_serie(ef, lambda i: dias_de(base_compras, "inventarios", i)),
            unidad="dias",
            formula=f"{dias} / (Costo de ventas / Inventarios)",
            insumos=["costo_ventas", "inventarios"],
            fuente=CARTILLA,
            nota="Cuanto tiempo la mercancia se queda en bodega antes de venderse.",
        ),
        Indicador(
            codigo="dias_proveedores",
            nombre="Dias de proveedores",
            categoria="Actividad",
            valores=_serie(ef, lambda i: dias_de(base_compras, "proveedores", i)),
            unidad="dias",
            formula=f"{dias} / (Compras / Proveedores)",
            insumos=[base_compras, "proveedores"],
            fuente=CARTILLA,
            nota="Cuanto se demora en pagarle a los proveedores." + proxy_compras,
        ),
        Indicador(
            codigo="ciclo_conversion_efectivo",
            nombre="Ciclo de conversion de efectivo",
            categoria="Actividad",
            valores=_serie(ef, ciclo),
            unidad="dias",
            formula="Dias de cartera + Dias de inventario - Dias de proveedores",
            insumos=["cuentas_por_cobrar", "inventarios", "proveedores"],
            fuente=GARCIA,
            nota="Dias que la plata pasa fuera de la caja. Entre mas alto, mas capital "
                 "de trabajo hay que financiar.",
        ),
        Indicador(
            codigo="ktno",
            nombre="Capital de trabajo neto operativo (KTNO)",
            categoria="Actividad",
            valores=_serie(ef, ktno),
            unidad="monto",
            formula="Cuentas por cobrar + Inventarios - Proveedores",
            insumos=["cuentas_por_cobrar", "inventarios", "proveedores"],
            fuente=GARCIA,
            nota="La plata inmovilizada para poder operar. Su AUMENTO consume caja.",
        ),
        Indicador(
            codigo="pkt",
            nombre="Productividad del capital de trabajo (PKT)",
            categoria="Actividad",
            valores=_serie(ef, lambda i: (
                None if ktno(i) is None else _div(ktno(i), ef.valor("ventas", i)) and
                _div(ktno(i), ef.valor("ventas", i)) * 100)),
            unidad="%",
            formula="KTNO / Ventas",
            insumos=["cuentas_por_cobrar", "inventarios", "proveedores", "ventas"],
            fuente=GARCIA,
            nota="Cuantos centavos de capital de trabajo exige cada peso vendido. "
                 "Entre mas bajo, mejor.",
        ),
        Indicador(
            codigo="rotacion_activos",
            nombre="Rotacion de activos totales",
            categoria="Actividad",
            valores=_serie(ef, lambda i: _div(ef.valor("ventas", i), ef.valor("activo_total", i))),
            unidad="veces",
            formula="Ventas / Activo total",
            insumos=["ventas", "activo_total"],
            fuente=BAENA,
            nota="Cuantos pesos vende la empresa por cada peso invertido en activos.",
        ),
    ]


# =============================================================== ENDEUDAMIENTO


def _endeudamiento(ef: EstadosFinancieros) -> list[Indicador]:
    def pasivo_implicito(i):
        a, p = ef.valor("activo_total", i), ef.valor("patrimonio", i)
        return None if None in (a, p) else a - p

    def pct(fn):
        def envuelto(i):
            v = fn(i)
            return None if v is None else v * 100
        return envuelto

    return [
        Indicador(
            codigo="endeudamiento_activo",
            nombre="Nivel de endeudamiento (sobre pasivo informado)",
            categoria="Endeudamiento",
            valores=_serie(ef, pct(lambda i: _div(ef.pasivo_total(i), ef.valor("activo_total", i)))),
            unidad="%",
            formula="Pasivo total / Activo total",
            insumos=["pasivo_corriente", "deuda_financiera_lp", "activo_total"],
            fuente=BAENA,
            nota="Que porcentaje de los activos esta financiado por terceros.",
        ),
        Indicador(
            codigo="endeudamiento_activo_implicito",
            nombre="Nivel de endeudamiento (pasivo implicito)",
            categoria="Endeudamiento",
            valores=_serie(ef, pct(lambda i: _div(pasivo_implicito(i), ef.valor("activo_total", i)))),
            unidad="%",
            formula="(Activo total - Patrimonio) / Activo total",
            insumos=["activo_total", "patrimonio"],
            fuente=BAENA,
            nota="Version que fuerza el cuadre del balance. Si difiere de la anterior, "
                 "es porque hay pasivos no informados. LA DIFERENCIA ENTRE AMBAS ES UN "
                 "DIAGNOSTICO EN SI MISMO.",
        ),
        Indicador(
            codigo="apalancamiento_total",
            nombre="Apalancamiento (Pasivo / Patrimonio)",
            categoria="Endeudamiento",
            valores=_serie(ef, lambda i: _div(ef.pasivo_total(i), ef.valor("patrimonio", i))),
            unidad="veces",
            formula="Pasivo total / Patrimonio",
            insumos=["pasivo_corriente", "deuda_financiera_lp", "patrimonio"],
            fuente=CARTILLA,
            nota="Cuantos pesos debe la empresa por cada peso de los socios.",
        ),
        Indicador(
            codigo="multiplicador_patrimonio",
            nombre="Multiplicador del patrimonio",
            categoria="Endeudamiento",
            valores=_serie(ef, lambda i: _div(ef.valor("activo_total", i), ef.valor("patrimonio", i))),
            unidad="veces",
            formula="Activo total / Patrimonio",
            insumos=["activo_total", "patrimonio"],
            fuente=CARTILLA,
            nota="Tercer factor del sistema DuPont.",
        ),
        Indicador(
            codigo="cobertura_intereses",
            nombre="Cobertura de intereses",
            categoria="Endeudamiento",
            valores=_serie(ef, lambda i: _div(ef.valor("utilidad_operacional", i), ef.valor("gastos_financieros", i))),
            unidad="veces",
            formula="Utilidad operacional (EBIT) / Gastos financieros",
            insumos=["utilidad_operacional", "gastos_financieros"],
            fuente=GARCIA,
            nota="Cuantas veces la operacion alcanza a pagar los intereses. "
                 "Por debajo de 2 veces se considera zona de riesgo.",
        ),
        Indicador(
            codigo="costo_deuda_implicito",
            nombre="Costo implicito de la deuda financiera",
            categoria="Endeudamiento",
            valores=_serie(ef, lambda i: (
                None if i == 0 or ef.deuda_financiera(i) is None or ef.deuda_financiera(i - 1) is None
                else _div(ef.valor("gastos_financieros", i),
                          (ef.deuda_financiera(i) + ef.deuda_financiera(i - 1)) / 2) * 100)),
            unidad="%",
            formula="Gastos financieros / Deuda financiera promedio del periodo",
            insumos=["gastos_financieros", "deuda_financiera_cp", "deuda_financiera_lp"],
            fuente=GARCIA,
            nota="Tasa efectiva que la empresa esta pagando. Solo se puede calcular "
                 "desde el segundo periodo (necesita saldo inicial y final).",
        ),
    ]


# ================================================================ RENTABILIDAD


def _rentabilidad(ef: EstadosFinancieros) -> list[Indicador]:
    def margen(cuenta):
        def fn(i):
            v = _div(ef.valor(cuenta, i), ef.valor("ventas", i))
            return None if v is None else v * 100
        return fn

    def tasa_impuestos(i):
        return _div(ef.valor("impuestos", i), ef.valor("utilidad_antes_impuestos", i))

    def uodi(i):
        ebit, t = ef.valor("utilidad_operacional", i), tasa_impuestos(i)
        return None if None in (ebit, t) else ebit * (1 - t)

    def capital_invertido(i):
        cxc, inv, prov = (ef.valor("cuentas_por_cobrar", i), ef.valor("inventarios", i),
                          ef.valor("proveedores", i))
        ppe = ef.valor("propiedad_planta_equipo", i)
        if any(v is None for v in (cxc, inv, prov, ppe)):
            return None
        return (cxc + inv - prov) + ppe

    return [
        Indicador(
            codigo="margen_bruto", nombre="Margen bruto", categoria="Rentabilidad",
            valores=_serie(ef, margen("utilidad_bruta")), unidad="%",
            formula="Utilidad bruta / Ventas", insumos=["utilidad_bruta", "ventas"],
            fuente=BAENA, nota="Lo que queda despues de pagar el costo de la mercancia.",
        ),
        Indicador(
            codigo="margen_operacional", nombre="Margen operacional", categoria="Rentabilidad",
            valores=_serie(ef, margen("utilidad_operacional")), unidad="%",
            formula="Utilidad operacional / Ventas", insumos=["utilidad_operacional", "ventas"],
            fuente=BAENA,
            nota="El margen del negocio en si, sin contar como esta financiado. "
                 "Garcia lo considera el renglon mas importante del estado de resultados.",
        ),
        Indicador(
            codigo="margen_neto", nombre="Margen neto", categoria="Rentabilidad",
            valores=_serie(ef, margen("utilidad_neta")), unidad="%",
            formula="Utilidad neta / Ventas", insumos=["utilidad_neta", "ventas"],
            fuente=BAENA, nota="Lo que finalmente queda para los socios.",
        ),
        Indicador(
            codigo="roa", nombre="ROA (rentabilidad del activo)", categoria="Rentabilidad",
            valores=_serie(ef, lambda i: (
                lambda v: None if v is None else v * 100
            )(_div(ef.valor("utilidad_operacional", i), ef.valor("activo_total", i)))),
            unidad="%",
            formula="Utilidad operacional (UAII) / Activo total",
            insumos=["utilidad_operacional", "activo_total"], fuente=CARTILLA,
            nota="Se usa la utilidad OPERACIONAL, no la neta, para medir el activo con "
                 "independencia de como este financiado. La cartilla del curso invierte "
                 "esta division en su ejemplo (ver FORMULAS.md).",
        ),
        Indicador(
            codigo="roe", nombre="ROE (rentabilidad del patrimonio)", categoria="Rentabilidad",
            valores=_serie(ef, lambda i: (
                lambda v: None if v is None else v * 100
            )(_div(ef.valor("utilidad_neta", i), ef.valor("patrimonio", i)))),
            unidad="%",
            formula="Utilidad neta / Patrimonio",
            insumos=["utilidad_neta", "patrimonio"], fuente=CARTILLA,
            nota="Lo que gana el socio por cada peso que tiene metido en la empresa.",
        ),
        Indicador(
            codigo="tasa_impuestos", nombre="Tasa efectiva de impuestos", categoria="Rentabilidad",
            valores=_serie(ef, lambda i: (lambda v: None if v is None else v * 100)(tasa_impuestos(i))),
            unidad="%", formula="Impuestos / Utilidad antes de impuestos",
            insumos=["impuestos", "utilidad_antes_impuestos"], fuente=BAENA,
        ),
        Indicador(
            codigo="uodi", nombre="UODI (utilidad operativa despues de impuestos)",
            categoria="Valor", valores=_serie(ef, uodi), unidad="monto",
            formula="UAII x (1 - tasa de impuestos)",
            insumos=["utilidad_operacional", "impuestos", "utilidad_antes_impuestos"],
            fuente=CARTILLA, nota="Insumo del EVA y del flujo de caja.",
        ),
        Indicador(
            codigo="capital_invertido", nombre="Capital invertido", categoria="Valor",
            valores=_serie(ef, capital_invertido), unidad="monto",
            formula="KTNO + Propiedad, planta y equipo",
            insumos=["cuentas_por_cobrar", "inventarios", "proveedores", "propiedad_planta_equipo"],
            fuente=GARCIA, nota="La plata realmente puesta a producir en el negocio.",
        ),
        Indicador(
            codigo="roic", nombre="ROIC (rentabilidad del capital invertido)", categoria="Valor",
            valores=_serie(ef, lambda i: (
                lambda v: None if v is None else v * 100
            )(_div(uodi(i), capital_invertido(i)))),
            unidad="%", formula="UODI / Capital invertido",
            insumos=["utilidad_operacional", "cuentas_por_cobrar", "inventarios",
                     "proveedores", "propiedad_planta_equipo"],
            fuente=GARCIA,
            nota="Si el ROIC no supera el costo del capital (WACC), la empresa destruye "
                 "valor aunque reporte utilidades.",
        ),
    ]


# ====================================================================== DUPONT


def dupont(ef: EstadosFinancieros) -> dict:
    """Descomposicion del ROE en sus tres palancas.

    ROE = Margen neto x Rotacion de activos x Multiplicador del patrimonio

    Permite responder: la rentabilidad cambio por precio, por eficiencia o por deuda.
    """
    filas = {"margen_neto": [], "rotacion_activos": [], "multiplicador_patrimonio": [], "roe_reconstruido": []}
    for i in range(ef.n_periodos):
        m = _div(ef.valor("utilidad_neta", i), ef.valor("ventas", i))
        r = _div(ef.valor("ventas", i), ef.valor("activo_total", i))
        a = _div(ef.valor("activo_total", i), ef.valor("patrimonio", i))
        filas["margen_neto"].append(m)
        filas["rotacion_activos"].append(r)
        filas["multiplicador_patrimonio"].append(a)
        filas["roe_reconstruido"].append(None if None in (m, r, a) else m * r * a * 100)

    # Que factor explica el cambio del ROE
    atribucion = None
    if ef.n_periodos >= 2 and all(filas[k][0] is not None and filas[k][-1] is not None
                                  for k in ("margen_neto", "rotacion_activos", "multiplicador_patrimonio")):
        atribucion = {}
        for k in ("margen_neto", "rotacion_activos", "multiplicador_patrimonio"):
            ini, fin = filas[k][0], filas[k][-1]
            atribucion[k] = (fin / ini - 1) * 100 if ini else None
    return {
        "formula": "ROE = (Utilidad neta / Ventas) x (Ventas / Activo total) x (Activo total / Patrimonio)",
        "fuente": CARTILLA,
        "factores": filas,
        "variacion_por_factor_pct": atribucion,
    }


# ============================================================ PUENTE DE CAJA


def puente_caja(ef: EstadosFinancieros) -> dict:
    """El analisis de Oscar Leon Garcia: la utilidad no es plata.

    Compara lo que el negocio genero contra lo que se trago el capital de
    trabajo y los activos fijos. Explica por que la empresa puede vender mas,
    reportar utilidades y aun asi quedarse sin caja.
    """
    if ef.n_periodos < 2:
        return {"disponible": False, "motivo": "Se requieren al menos dos periodos."}

    ini, fin = 0, ef.n_periodos - 1

    def ktno(i):
        piezas = [ef.valor("cuentas_por_cobrar", i), ef.valor("inventarios", i), ef.valor("proveedores", i)]
        return None if any(p is None for p in piezas) else piezas[0] + piezas[1] - piezas[2]

    tasa = _div(ef.valor("impuestos", fin), ef.valor("utilidad_antes_impuestos", fin))
    ebit = ef.valor("utilidad_operacional", fin)
    uodi = None if None in (ebit, tasa) else ebit * (1 - tasa)

    d_ktno = None if None in (ktno(fin), ktno(ini)) else ktno(fin) - ktno(ini)
    ppe_ini, ppe_fin = ef.valor("propiedad_planta_equipo", ini), ef.valor("propiedad_planta_equipo", fin)
    d_ppe = None if None in (ppe_ini, ppe_fin) else ppe_fin - ppe_ini
    ef_ini, ef_fin = ef.valor("efectivo", ini), ef.valor("efectivo", fin)
    d_efectivo = None if None in (ef_ini, ef_fin) else ef_fin - ef_ini
    df_ini, df_fin = ef.deuda_financiera(ini), ef.deuda_financiera(fin)
    d_deuda = None if None in (df_ini, df_fin) else df_fin - df_ini

    tiene_depreciacion = ef.existe("depreciacion")
    brecha = None
    if None not in (uodi, d_ktno, d_ppe):
        brecha = uodi - d_ktno - d_ppe

    return {
        "disponible": True,
        "periodo": f"{ef.periodos[ini]} -> {ef.periodos[fin]}",
        "uodi": uodi,
        "aumento_ktno": d_ktno,
        "aumento_activos_fijos_neto": d_ppe,
        "flujo_caja_libre_aprox": brecha,
        "variacion_efectivo": d_efectivo,
        "variacion_deuda_financiera": d_deuda,
        "es_aproximacion": not tiene_depreciacion,
        "advertencia": (
            "Aproximacion: no se informo la depreciacion, por lo que no se puede "
            "sumar al flujo de caja bruto ni separar el CAPEX de reposicion del de "
            "crecimiento. El resultado subestima el flujo real."
        ) if not tiene_depreciacion else "",
        "formula": "FCL = UODI + Depreciacion - Aumento KTNO - Inversion en activos fijos",
        "fuente": GARCIA,
    }


# ================================================================ ORQUESTADOR


def calcular_todos(ef: EstadosFinancieros) -> dict[str, Indicador]:
    """Devuelve todos los indicadores individuales indexados por codigo."""
    lista = _liquidez(ef) + _actividad(ef) + _endeudamiento(ef) + _rentabilidad(ef)
    return {ind.codigo: ind for ind in lista}


def calcular_completo(ef: EstadosFinancieros) -> dict:
    """Paquete completo: indicadores + analisis estructurales."""
    return {
        "empresa": ef.empresa,
        "periodos": ef.periodos,
        "moneda": ef.moneda,
        "unidad": ef.unidad,
        "indicadores": calcular_todos(ef),
        "vertical": analisis_vertical(ef),
        "horizontal": analisis_horizontal(ef),
        "dupont": dupont(ef),
        "puente_caja": puente_caja(ef),
    }
