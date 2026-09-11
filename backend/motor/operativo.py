"""Punto de equilibrio y grados de apalancamiento (GAO, GAF, GAT).

Son los indicadores del modulo 2 de la cartilla que NO salen de un estado
financiero: necesitan separar los costos fijos de los variables, y un balance
o un estado de resultados publicado no trae esa separacion. Por eso viven en
una calculadora aparte donde el usuario digita los datos, igual que la de
proyectos de inversion, en vez de inventarse desde las 23 cuentas.

Todo es determinista: mismas entradas, mismas salidas. Cada resultado viaja
con su formula, su fuente y una lectura en prosa que sale de reglas, no de
un modelo.

DECISIONES
----------
**El GAF usa la formula estandar** UAII / (UAII - intereses). La cartilla
mete los dividendos preferentes en el denominador -GAF = UAII / (UAII - I -
D/(1-t))- y con sus propios datos llega a 1,3 cuando esa formula da 2,04
(FORMULAS.md §8.2). Se calculan las dos y se muestran las dos, con la
estandar como principal, para que en la sustentacion se pueda explicar la
diferencia en vez de esconderla.

**Si el costo variable unitario iguala o supera el precio, no hay punto de
equilibrio.** Cada unidad pierde plata y vender mas solo agranda la perdida.
Se avisa con esas palabras en vez de devolver un numero negativo, que es lo
que la cartilla advierte que "no es logico".

Fuente: Barbosa Guerrero (2021), modulo 2; Baena Toro (2014) cap. 8.
"""

from __future__ import annotations

CARTILLA = "Barbosa Guerrero, L. M. (2021). Análisis y gerencia financiera, U. El Bosque, módulo 2"
BAENA = "Baena Toro, D. (2014). Análisis financiero: enfoque y proyecciones"


def _num(v: float, dec: int = 0) -> str:
    """Numero a la colombiana: punto de miles, coma decimal."""
    s = f"{v:,.{dec}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(v: float, dec: int = 1) -> str:
    return _num(v * 100, dec) + " %"


# ======================================================= PUNTO DE EQUILIBRIO


def punto_equilibrio(precio: float, costo_variable_unitario: float, costos_fijos: float,
                     unidades_programadas: float | None = None) -> dict:
    """PEU = CF / (P - CVU);  PE$ = CF / (1 - CVU/P).

    Con las unidades programadas se agrega el margen de seguridad: cuanto
    pueden caer las ventas antes de entrar en perdida.
    """
    if precio is None or costo_variable_unitario is None or costos_fijos is None:
        raise ValueError("Faltan datos: precio, costo variable unitario y costos fijos.")
    if precio <= 0:
        raise ValueError("El precio de venta debe ser mayor que cero.")
    if costo_variable_unitario < 0 or costos_fijos < 0:
        raise ValueError("Los costos no pueden ser negativos.")

    mc_unitario = precio - costo_variable_unitario
    razon_mc = mc_unitario / precio

    if mc_unitario <= 0:
        raise ValueError(
            "El costo variable por unidad ({}) iguala o supera el precio ({}): cada "
            "unidad pierde plata y vender más solo agranda la pérdida. No existe punto "
            "de equilibrio; hay que subir el precio o bajar el costo variable.".format(
                _num(costo_variable_unitario), _num(precio)))

    peu = costos_fijos / mc_unitario
    pe_pesos = costos_fijos / razon_mc

    salida = {
        "entradas": {
            "precio": precio, "costo_variable_unitario": costo_variable_unitario,
            "costos_fijos": costos_fijos, "unidades_programadas": unidades_programadas,
        },
        "margen_contribucion_unitario": mc_unitario,
        "razon_margen_contribucion": razon_mc,
        "punto_equilibrio_unidades": peu,
        "punto_equilibrio_pesos": pe_pesos,
        "formulas": {
            "punto_equilibrio_unidades": "PEU = Costos fijos / (Precio − Costo variable unitario)",
            "punto_equilibrio_pesos": "PE$ = Costos fijos / (1 − Costo variable unitario / Precio)",
            "margen_seguridad": "(Unidades programadas − PEU) / Unidades programadas",
        },
        "fuente": CARTILLA,
    }

    lectura = (
        f"Hay que vender {_num(peu, 1)} unidades —{_num(pe_pesos)} en pesos— para "
        f"cubrir los costos fijos de {_num(costos_fijos)}. Cada unidad aporta "
        f"{_num(mc_unitario)} de margen de contribución ({_pct(razon_mc)} del precio)."
    )

    if unidades_programadas is not None and unidades_programadas > 0:
        utilidad = unidades_programadas * mc_unitario - costos_fijos
        margen_seg = (unidades_programadas - peu) / unidades_programadas
        salida.update({
            "utilidad_operativa_programada": utilidad,
            "margen_seguridad": margen_seg,
            "cubre_costos": unidades_programadas >= peu,
        })
        if unidades_programadas >= peu:
            lectura += (
                f" Con las {_num(unidades_programadas)} unidades programadas la operación "
                f"deja {_num(utilidad)} de utilidad operativa y las ventas pueden caer "
                f"hasta {_pct(margen_seg)} antes de entrar en pérdida."
            )
        else:
            lectura += (
                f" Con las {_num(unidades_programadas)} unidades programadas NO se alcanza "
                f"el equilibrio: faltan {_num(peu - unidades_programadas, 1)} unidades y la "
                f"operación pierde {_num(-utilidad)}."
            )
    salida["lectura"] = lectura
    return salida


# ===================================================== GRADOS DE APALANCAMIENTO


def apalancamiento(ventas: float, costos_variables: float, costos_fijos: float,
                   intereses: float = 0.0, tasa_impuestos: float | None = None,
                   dividendos_preferentes: float = 0.0) -> dict:
    """GAO = MC / UAII;  GAF = UAII / (UAII − I);  GAT = GAO × GAF.

    Tambien arma el estado de resultados hasta la utilidad neta, que es lo
    que la cartilla hace en Excel antes de calcular.
    """
    for nombre, v in (("ventas", ventas), ("costos_variables", costos_variables),
                      ("costos_fijos", costos_fijos)):
        if v is None:
            raise ValueError(f"Falta el dato: {nombre}.")
        if v < 0:
            raise ValueError(f"{nombre} no puede ser negativo.")
    intereses = intereses or 0.0
    dividendos_preferentes = dividendos_preferentes or 0.0

    mc = ventas - costos_variables
    uaii = mc - costos_fijos
    uai = uaii - intereses
    impuestos = uai * tasa_impuestos if (tasa_impuestos is not None and uai > 0) else 0.0
    utilidad_neta = uai - impuestos

    gao = mc / uaii if uaii > 0 else None
    gaf = uaii / uai if (uaii > 0 and uai > 0) else None
    gat = gao * gaf if (gao is not None and gaf is not None) else None

    # La variante de la cartilla, con dividendos preferentes antes de impuestos.
    gaf_cartilla = None
    if uaii > 0 and dividendos_preferentes > 0 and tasa_impuestos is not None and tasa_impuestos < 1:
        den = uaii - intereses - dividendos_preferentes / (1 - tasa_impuestos)
        gaf_cartilla = uaii / den if den > 0 else None

    salida = {
        "entradas": {
            "ventas": ventas, "costos_variables": costos_variables, "costos_fijos": costos_fijos,
            "intereses": intereses, "tasa_impuestos": tasa_impuestos,
            "dividendos_preferentes": dividendos_preferentes,
        },
        "estado_resultados": [
            {"renglon": "Ventas", "valor": ventas},
            {"renglon": "− Costos variables", "valor": -costos_variables},
            {"renglon": "= Margen de contribución", "valor": mc, "total": True},
            {"renglon": "− Costos y gastos fijos de operación", "valor": -costos_fijos},
            {"renglon": "= Utilidad operacional (UAII)", "valor": uaii, "total": True},
            {"renglon": "− Intereses", "valor": -intereses},
            {"renglon": "= Utilidad antes de impuestos", "valor": uai, "total": True},
            {"renglon": "− Impuestos", "valor": -impuestos},
            {"renglon": "= Utilidad neta", "valor": utilidad_neta, "total": True},
        ],
        "margen_contribucion": mc,
        "uaii": uaii,
        "utilidad_neta": utilidad_neta,
        "gao": gao,
        "gaf": gaf,
        "gat": gat,
        "gaf_cartilla": gaf_cartilla,
        "formulas": {
            "gao": "GAO = Margen de contribución / UAII",
            "gaf": "GAF = UAII / (UAII − Intereses)",
            "gat": "GAT = GAO × GAF",
            "gaf_cartilla": "GAF (cartilla) = UAII / (UAII − Intereses − Dividendos / (1 − t))",
        },
        "fuente": BAENA,
        "nota_gaf": (
            "Se muestra como principal la fórmula estándar del GAF. La cartilla del curso "
            "incluye los dividendos preferentes en el denominador; con sus propios datos "
            "esa fórmula da 2,04 y no el 1,3 que reporta (ver FORMULAS.md §8.2)."
        ),
    }

    if uaii <= 0:
        salida["lectura"] = (
            f"El margen de contribución ({_num(mc)}) no alcanza a cubrir los costos fijos "
            f"({_num(costos_fijos)}): la operación pierde {_num(-uaii)} antes de intereses. "
            f"Sin utilidad operativa los grados de apalancamiento no tienen sentido; primero "
            f"hay que pasar el punto de equilibrio."
        )
    elif gaf is None:
        salida["lectura"] = (
            f"La operación deja {_num(uaii)} de UAII, pero los intereses ({_num(intereses)}) "
            f"se la comen entera. GAO = {_num(gao, 2)}: cada 1 % más de ventas mueve la UAII "
            f"{_num(gao, 2)} %. El apalancamiento financiero no se puede medir con pérdida "
            f"antes de impuestos."
        )
    else:
        salida["lectura"] = (
            f"Cada 1 % de cambio en las ventas mueve la utilidad operativa {_num(gao, 2)} % "
            f"(GAO) y, por la deuda, la utilidad del socio {_num(gat, 2)} % (GAT = "
            f"{_num(gao, 2)} × {_num(gaf, 2)}). "
            + ("Sin deuda el GAF es 1: todo el apalancamiento es operativo."
               if intereses == 0 else
               f"El GAF de {_num(gaf, 2)} dice que la deuda amplifica el resultado del socio "
               f"en ambas direcciones: ayuda cuando las ventas suben y castiga cuando bajan.")
        )
    return salida
