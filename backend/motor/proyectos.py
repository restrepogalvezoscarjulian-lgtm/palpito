"""Evaluación financiera de proyectos de inversión.

Sesion 6 del curso (2 de septiembre de 2026): el profesor pidio integrar al
diagnosticador un modulo que evalue proyectos con VPN, TIR, payback descontado
e índice de rentabilidad, más un flujo de caja mensual a 12 meses y escenarios.

Como todo el motor, esto es determinista: mismas entradas, mismas salidas,
sin intervencion de ningun modelo de lenguaje. El modelo recibe estos números
ya resueltos y solo los traduce a prosa.

Criterios y fuentes en FÓRMULAS.md sección 9.
"""

from __future__ import annotations

from dataclasses import dataclass, field

GARCIA = "Garcia S., O. L. Administración financiera: fundamentos y aplicaciones"
CARTILLA = "Barbosa Guerrero, L. M. (2021). Análisis y gerencia financiera, U. El Bosque"
SESION6 = "Sesion 6 del curso (2 de septiembre de 2026)"

# Tolerancia y tope de iteraciones para la busqueda de raices de la TIR.
_TOL = 1e-9
_MAX_ITER = 300


# ================================================================ ESTRUCTURAS


@dataclass
class Metrica:
    """Un indicador de proyecto con su trazabilidad completa.

    Igual que los indicadores del diagnóstico: cada metrica carga su fórmula,
    sus insumos, el criterio de aceptación y la fuente. Así el puntaje del
    proyecto se puede discutir renglon por renglon.
    """

    codigo: str
    nombre: str
    valor: float | None
    unidad: str = "veces"
    formula: str = ""
    insumos: list[str] = field(default_factory=list)
    fuente: str = ""
    criterio: str = ""
    veredicto: str = "sin_dato"  # "favorable" | "limite" | "desfavorable"
    lectura: str = ""
    ayuda: str = ""

    @property
    def disponible(self) -> bool:
        return self.valor is not None


@dataclass
class Proyecto:
    """Los datos de entrada de un proyecto de inversión.

    `flujos` son los flujos de caja libres por periodo SIN incluir la inversión
    inicial: esta viaja aparte en `inversión` como número positivo. Se separan
    a proposito porque el índice de rentabilidad necesita distinguirlos, y
    porque confundir el signo de la inversión es el error más comun del tema.
    """

    nombre: str = "Proyecto sin nombre"
    inversion: float = 0.0
    flujos: list[float] = field(default_factory=list)
    tasa_descuento: float = 0.0          # WACC en tanto por uno (0.10 = 10%)
    plazo_exigido: float | None = None   # anios maximos que exige la junta
    moneda: str = "COP"
    unidad: str = "millones"

    @property
    def horizonte(self) -> int:
        return len(self.flujos)

    def serie_completa(self) -> list[float]:
        """Flujos con la inversión en t=0 y signo negativo."""
        return [-abs(self.inversion)] + list(self.flujos)


# ======================================================================= WACC


def calcular_wacc(
    patrimonio: float | None,
    deuda: float | None,
    costo_patrimonio: float | None,
    costo_deuda: float | None,
    tasa_impuestos: float | None,
) -> dict:
    """Costo promedio ponderado de capital.

    WACC = E/(D+E) * Ke + D/(D+E) * Kd * (1 - t)

    El escudo fiscal solo se aplica al costo de la deuda porque los intereses
    son deducibles y los dividendos no. Es la razón de fondo por la que la
    deuda "cuesta menos" que el patrimonio, y por la que los intereses NO se
    vuelven a restar dentro del flujo de caja del proyecto: ya están aquí.
    """
    faltantes = [
        nombre
        for nombre, valor in (
            ("patrimonio", patrimonio),
            ("deuda", deuda),
            ("costo_patrimonio", costo_patrimonio),
            ("costo_deuda", costo_deuda),
            ("tasa_impuestos", tasa_impuestos),
        )
        if valor is None
    ]
    if faltantes:
        return {"valor": None, "faltantes": faltantes}

    capital = patrimonio + deuda
    if capital == 0:
        return {"valor": None, "faltantes": ["capital total en cero"]}

    peso_patrimonio = patrimonio / capital
    peso_deuda = deuda / capital
    aporte_patrimonio = peso_patrimonio * costo_patrimonio
    aporte_deuda = peso_deuda * costo_deuda * (1 - tasa_impuestos)

    return {
        "valor": aporte_patrimonio + aporte_deuda,
        "faltantes": [],
        "peso_patrimonio": peso_patrimonio,
        "peso_deuda": peso_deuda,
        "aporte_patrimonio": aporte_patrimonio,
        "aporte_deuda": aporte_deuda,
        "escudo_fiscal": peso_deuda * costo_deuda * tasa_impuestos,
        "formula": "WACC = E/(D+E) x Ke + D/(D+E) x Kd x (1 - t)",
        "fuente": GARCIA,
    }


# ================================================================ DESCUENTOS


def valor_presente(flujo: float, tasa: float, periodo: int) -> float:
    """VP = VF / (1 + i)^t. La fórmula que el profesor dicto en Excel."""
    return flujo / ((1 + tasa) ** periodo)


def flujos_descontados(proyecto: Proyecto) -> list[dict]:
    """Detalle periodo a periodo: flujo, factor, valor presente y acumulado.

    Se devuelve la tabla completa y no solo el total porque el payback se lee
    de ella, y porque el usuario tiene que poder verificar cada renglon contra
    su propio Excel. Ese fue el encargo explicito de la sesion 5.
    """
    tasa = proyecto.tasa_descuento
    filas = []
    acumulado = 0.0
    for periodo, flujo in enumerate(proyecto.serie_completa()):
        factor = 1 / ((1 + tasa) ** periodo)
        vp = flujo * factor
        acumulado += vp
        filas.append(
            {
                "periodo": periodo,
                "flujo": flujo,
                "factor": factor,
                "valor_presente": vp,
                "acumulado": acumulado,
            }
        )
    return filas


def valor_presente_neto(proyecto: Proyecto) -> float:
    """VPN = suma de los flujos descontados, inversión incluida en t=0."""
    return sum(f["valor_presente"] for f in flujos_descontados(proyecto))


def valor_presente_flujos(proyecto: Proyecto) -> float:
    """Valor presente de los flujos futuros SIN la inversión.

    Es el numerador del índice de rentabilidad. En el ejercicio de la
    panaderia Espiga este es el 1.706 que el profesor cálculo en clase.
    """
    return sum(
        valor_presente(flujo, proyecto.tasa_descuento, periodo + 1)
        for periodo, flujo in enumerate(proyecto.flujos)
    )


# ======================================================================== TIR


def _vpn_a_tasa(serie: list[float], tasa: float) -> float:
    if tasa <= -1:
        return float("inf")
    return sum(f / ((1 + tasa) ** t) for t, f in enumerate(serie))


def tasa_interna_retorno(proyecto: Proyecto) -> float | None:
    """TIR: la tasa que hace el VPN igual a cero.

    Se resuelve por biseccion y no con la fórmula cerrada porque para más de
    dos periodos no existe fórmula cerrada: es un polinomio. La biseccion es
    lenta comparada con Newton pero no se escapa, y aquí son cuatro o cinco
    periodos, no un millon.

    Devuelve None si los flujos no cambian de signo (sin cambio de signo no
    hay raiz: un proyecto que solo recibe plata no tiene "rentabilidad", tiene
    un regalo) o si la raiz no cae en el rango razonable.
    """
    serie = proyecto.serie_completa()
    if not serie or all(f >= 0 for f in serie) or all(f <= 0 for f in serie):
        return None

    bajo, alto = -0.9999, 10.0
    v_bajo, v_alto = _vpn_a_tasa(serie, bajo), _vpn_a_tasa(serie, alto)
    if v_bajo * v_alto > 0:
        return None

    for _ in range(_MAX_ITER):
        medio = (bajo + alto) / 2
        v_medio = _vpn_a_tasa(serie, medio)
        if abs(v_medio) < _TOL or (alto - bajo) < _TOL:
            return medio
        if v_bajo * v_medio < 0:
            alto, v_alto = medio, v_medio
        else:
            bajo, v_bajo = medio, v_medio
    return (bajo + alto) / 2


def tir_modificada(
    proyecto: Proyecto,
    tasa_reinversion: float | None = None,
    tasa_financiacion: float | None = None,
) -> float | None:
    """TIR modificada: corrige el supuesto de reinversión de la TIR.

    El profesor señaló la debilidad exacta que esto resuelve: la TIR "supone
    la reinversión de los flujos futuros a esa misma tasa". Si un proyecto
    rinde 40%, la TIR asume que cada peso que sale se vuelve a invertir al
    40%, lo cual casi nunca es cierto. La TIRM reinvierte al WACC, que es lo
    que la empresa realmente consigue.

    TIRM = (VF de los positivos / VP de los negativos)^(1/n) - 1
    """
    reinversion = proyecto.tasa_descuento if tasa_reinversion is None else tasa_reinversion
    financiacion = proyecto.tasa_descuento if tasa_financiacion is None else tasa_financiacion
    serie = proyecto.serie_completa()
    n = len(serie) - 1
    if n <= 0:
        return None

    vf_positivos = sum(
        f * ((1 + reinversion) ** (n - t)) for t, f in enumerate(serie) if f > 0
    )
    vp_negativos = sum(
        -f / ((1 + financiacion) ** t) for t, f in enumerate(serie) if f < 0
    )
    if vp_negativos <= 0 or vf_positivos <= 0:
        return None
    return (vf_positivos / vp_negativos) ** (1 / n) - 1


# ==================================================================== PAYBACK


def _payback(acumulados: list[float], aportes: list[float]) -> float | None:
    """Año en que el acumulado cruza cero, interpolando dentro del año.

    Fórmula de la sesion 6: año antes de recuperar + (inversión - acumulado)
    / flujo del año de recuperación.
    """
    for periodo in range(1, len(acumulados)):
        if acumulados[periodo] >= 0:
            faltante = -acumulados[periodo - 1]
            aporte = aportes[periodo]
            if aporte <= 0:
                return float(periodo)
            return (periodo - 1) + faltante / aporte
    return None


def payback_simple(proyecto: Proyecto) -> float | None:
    """Años para recuperar la inversión sin descontar los flujos."""
    serie = proyecto.serie_completa()
    acumulados, corriente = [], 0.0
    for flujo in serie:
        corriente += flujo
        acumulados.append(corriente)
    return _payback(acumulados, serie)


def payback_descontado(proyecto: Proyecto) -> float | None:
    """Igual que el simple pero sobre flujos traidos a valor presente.

    Es el que importa: en el ejercicio de Espiga el payback simple da 3,00
    años justos (cumple el plazo de la junta) y el descontado da 3,57 (no lo
    cumple). Esa diferencia es la que cambia la recomendacion, y por eso el
    modulo reporta los dos y no solo uno.
    """
    filas = flujos_descontados(proyecto)
    acumulados = [f["acumulado"] for f in filas]
    aportes = [f["valor_presente"] for f in filas]
    return _payback(acumulados, aportes)


def indice_rentabilidad(proyecto: Proyecto) -> float | None:
    """IR = valor presente de los flujos futuros / inversión inicial.

    Cuánto valor presente genera cada peso invertido. Es el criterio que manda
    cuando el presupuesto esta racionado y hay que escoger entre proyectos.
    """
    inversion = abs(proyecto.inversion)
    if inversion == 0:
        return None
    return valor_presente_flujos(proyecto) / inversion


# ============================================================= FLUJO MENSUAL


def flujo_caja_mensual(saldo_inicial: float, meses: list[dict]) -> dict:
    """Flujo de caja a 12 meses, mes a mes, con deteccion de faltantes.

    Cada mes entra como {"mes": "Enero", "entradas": {...}, "salidas": {...}}.
    El saldo final de un mes es el inicial del siguiente: ese encadenamiento
    es todo el punto del ejercicio. Un proyecto puede tener VPN positivo y aún
    así quebrar la empresa si la caja se agota en marzo, que fue justamente el
    caso que el profesor puso en clase.
    """
    filas = []
    saldo = saldo_inicial
    for mes in meses:
        entradas = {k: float(v) for k, v in mes.get("entradas", {}).items()}
        salidas = {k: float(v) for k, v in mes.get("salidas", {}).items()}
        total_entradas = sum(entradas.values())
        total_salidas = sum(salidas.values())
        neto = total_entradas - total_salidas
        saldo_inicial_mes = saldo
        saldo = saldo_inicial_mes + neto
        filas.append(
            {
                "mes": mes.get("mes", f"Mes {len(filas) + 1}"),
                "saldo_inicial": saldo_inicial_mes,
                "entradas": entradas,
                "salidas": salidas,
                "total_entradas": total_entradas,
                "total_salidas": total_salidas,
                "flujo_neto": neto,
                "saldo_final": saldo,
                "deficit": saldo < 0,
            }
        )

    meses_deficit = [f for f in filas if f["deficit"]]
    saldo_minimo = min((f["saldo_final"] for f in filas), default=saldo_inicial)
    faltante = abs(min(saldo_minimo, 0.0))

    if meses_deficit:
        primero = meses_deficit[0]["mes"]
        lectura = (
            f"La caja se agota en {primero}. El faltante máximo del año es "
            f"{faltante:,.1f}, que es el monto mínimo que habría que conseguir "
            f"o diferir para sostener la operación."
        )
    else:
        lectura = (
            f"La caja nunca se agota. El punto más ajustado del año deja "
            f"{saldo_minimo:,.1f} de saldo."
        )

    return {
        "saldo_inicial": saldo_inicial,
        "meses": filas,
        "saldo_final": saldo,
        "saldo_minimo": saldo_minimo,
        "meses_en_deficit": [f["mes"] for f in meses_deficit],
        "faltante_maximo": faltante,
        "hay_deficit": bool(meses_deficit),
        "lectura": lectura,
        "fuente": SESION6,
    }


# =================================================== ESCENARIOS Y SENSIBILIDAD


def aplicar_escenario(proyecto: Proyecto, variacion: float) -> Proyecto:
    """Copia del proyecto con los flujos movidos un porcentaje.

    La inversión NO se mueve: ya esta comprometida. Lo que es incierto son los
    ingresos futuros, y mover ambos a la vez escondería el riesgo real.
    """
    return Proyecto(
        nombre=proyecto.nombre,
        inversion=proyecto.inversion,
        flujos=[f * (1 + variacion) for f in proyecto.flujos],
        tasa_descuento=proyecto.tasa_descuento,
        plazo_exigido=proyecto.plazo_exigido,
        moneda=proyecto.moneda,
        unidad=proyecto.unidad,
    )


def escenarios(
    proyecto: Proyecto,
    conservador: float = -0.20,
    optimista: float = 0.20,
) -> list[dict]:
    """Conservador, base y optimista.

    Un VPN positivo en un solo escenario no es una decisión: hay que saber
    cuánto puede fallar el presupuesto antes de destruir valor.
    """
    definiciones = [
        ("conservador", "Conservador", conservador),
        ("base", "Base", 0.0),
        ("optimista", "Optimista", optimista),
    ]
    salida = []
    for codigo, nombre, variacion in definiciones:
        variante = aplicar_escenario(proyecto, variacion)
        vpn = valor_presente_neto(variante)
        salida.append(
            {
                "codigo": codigo,
                "nombre": nombre,
                "variacion_flujos": variacion,
                "vpn": vpn,
                "tir": tasa_interna_retorno(variante),
                "indice_rentabilidad": indice_rentabilidad(variante),
                "payback_descontado": payback_descontado(variante),
                "crea_valor": vpn > 0,
            }
        )
    return salida


def punto_de_quiebre(proyecto: Proyecto) -> dict:
    """Cuánto pueden caer los flujos antes de que el VPN llegue a cero.

    Es la holgura del proyecto expresada en una sola cifra. Un proyecto que
    aguanta una caida del 30% es robusto; uno que se cae con el 2% es una
    apuesta, por más que su VPN sea positivo.

    Como el VPN es lineal en la variacion de los flujos, la holgura sale
    directo: VPN(v) = VP_flujos x (1+v) - inversión, y se despeja v.
    """
    vp_flujos = valor_presente_flujos(proyecto)
    inversion = abs(proyecto.inversion)
    if vp_flujos <= 0:
        return {"holgura": None, "lectura": "Sin flujos futuros positivos que evaluar."}

    holgura = (inversion / vp_flujos) - 1  # negativo si el proyecto crea valor
    if holgura >= 0:
        lectura = (
            f"El proyecto ya destruye valor: los flujos tendrian que subir "
            f"{holgura * 100:.1f}% solo para empatar."
        )
    else:
        lectura = (
            f"Los flujos pueden caer hasta {abs(holgura) * 100:.1f}% antes de "
            f"que el proyecto deje de crear valor."
        )
    return {
        "holgura": holgura,
        "caida_tolerada": abs(holgura) if holgura < 0 else 0.0,
        "vp_flujos": vp_flujos,
        "inversion": inversion,
        "lectura": lectura,
        "formula": "Caida tolerada = 1 - (Inversión / VP de los flujos)",
        "fuente": SESION6,
    }


# =============================================== METRICAS CON SU SEMAFORO


def _semaforo_vpn(vpn: float | None) -> str:
    if vpn is None:
        return "sin_dato"
    if vpn > 0:
        return "favorable"
    return "limite" if vpn == 0 else "desfavorable"


def _metricas(proyecto: Proyecto) -> list[Metrica]:
    tasa = proyecto.tasa_descuento
    vpn = valor_presente_neto(proyecto)
    tir = tasa_interna_retorno(proyecto)
    tirm = tir_modificada(proyecto)
    pb_simple = payback_simple(proyecto)
    pb_desc = payback_descontado(proyecto)
    ir = indice_rentabilidad(proyecto)
    vp_flujos = valor_presente_flujos(proyecto)
    plazo = proyecto.plazo_exigido

    def veredicto_payback(valor: float | None) -> str:
        if valor is None:
            return "desfavorable"  # no se recupera dentro del horizonte
        if plazo is None:
            return "favorable"
        if valor <= plazo:
            return "favorable"
        return "limite" if valor <= plazo * 1.15 else "desfavorable"

    def veredicto_tasa(valor: float | None) -> str:
        if valor is None:
            return "sin_dato"
        if valor > tasa:
            return "favorable"
        return "limite" if abs(valor - tasa) < 1e-9 else "desfavorable"

    metricas = [
        Metrica(
            codigo="vpn",
            nombre="Valor presente neto (VPN)",
            valor=vpn,
            unidad=proyecto.unidad,
            formula="VPN = suma de FCt / (1 + WACC)^t, con la inversión en t=0",
            insumos=["inversion", "flujos", "tasa_descuento"],
            fuente=SESION6,
            criterio="Crea valor si VPN > 0",
            veredicto=_semaforo_vpn(vpn),
            lectura=(
                f"El proyecto devuelve la inversión, paga el {tasa * 100:.1f}% "
                f"exigido de costo de capital y agrega {vpn:,.1f} de valor."
                if vpn > 0
                else f"El proyecto no alcanza a cubrir el {tasa * 100:.1f}% "
                f"exigido: destruye {abs(vpn):,.1f} de valor."
            ),
            ayuda=(
                "Cuánto valor en pesos de hoy agrega el proyecto después de "
                "pagar el costo del capital. Es el criterio principal: mide "
                "creacion de valor, pero no dice a que tasa rinde."
            ),
        ),
        Metrica(
            codigo="vp_flujos",
            nombre="Valor presente de los flujos futuros",
            valor=vp_flujos,
            unidad=proyecto.unidad,
            formula="VP = suma de FCt / (1 + WACC)^t, sin la inversión",
            insumos=["flujos", "tasa_descuento"],
            fuente=SESION6,
            criterio="Se compara contra la inversión inicial",
            veredicto="favorable" if vp_flujos > abs(proyecto.inversion) else "desfavorable",
            lectura=(
                f"Los flujos futuros valen hoy {vp_flujos:,.1f} frente a una "
                f"inversión de {abs(proyecto.inversion):,.1f}."
            ),
            ayuda=(
                "Lo que valen hoy todos los ingresos futuros del proyecto. Es "
                "el número que se compara contra la inversión para saber si "
                "vale la pena."
            ),
        ),
        Metrica(
            codigo="tir",
            nombre="Tasa interna de retorno (TIR)",
            valor=tir,
            unidad="porcentaje",
            formula="Tasa que hace VPN = 0",
            insumos=["inversion", "flujos"],
            fuente=SESION6,
            criterio=f"Se acepta si TIR > WACC ({tasa * 100:.1f}%)",
            veredicto=veredicto_tasa(tir),
            lectura=(
                f"El proyecto rinde {tir * 100:.2f}% anual frente a un costo de "
                f"capital de {tasa * 100:.1f}%."
                if tir is not None
                else "No se puede calcular: los flujos no cambian de signo."
            ),
            ayuda=(
                "La rentabilidad anual propia del proyecto. Es intuitiva y "
                "comparable con tasas de mercado, pero ignora el tamaño del "
                "proyecto y supone que los flujos se reinvierten a esa misma tasa."
            ),
        ),
        Metrica(
            codigo="tir_modificada",
            nombre="TIR modificada (TIRM)",
            valor=tirm,
            unidad="porcentaje",
            formula="TIRM = (VF de los flujos positivos / VP de los negativos)^(1/n) - 1",
            insumos=["inversion", "flujos", "tasa_descuento"],
            fuente=SESION6,
            criterio=f"Se acepta si TIRM > WACC ({tasa * 100:.1f}%)",
            veredicto=veredicto_tasa(tirm),
            lectura=(
                f"Reinvirtiendo los flujos al {tasa * 100:.1f}% y no a la propia "
                f"TIR, el proyecto rinde {tirm * 100:.2f}%."
                if tirm is not None
                else "No se puede calcular con los flujos dados."
            ),
            ayuda=(
                "Corrige el supuesto irreal de la TIR: en vez de asumir que "
                "cada peso que sale se reinvierte a la tasa del proyecto, "
                "asume que se reinvierte al costo de capital. Suele ser más "
                "baja que la TIR y más creible."
            ),
        ),
        Metrica(
            codigo="payback_simple",
            nombre="Payback simple",
            valor=pb_simple,
            unidad="anios",
            formula="Año antes de recuperar + (pendiente / flujo del año)",
            insumos=["inversion", "flujos"],
            fuente=SESION6,
            criterio=(
                f"Se acepta si es menor a {plazo:g} años"
                if plazo is not None
                else "Sin plazo exigido definido"
            ),
            veredicto=veredicto_payback(pb_simple),
            lectura=(
                f"Sin descontar, la inversión se recupera en {pb_simple:.2f} años."
                if pb_simple is not None
                else "La inversión no se recupera dentro del horizonte evaluado."
            ),
            ayuda=(
                "Cuántos años tarda el proyecto en devolver la inversión, "
                "sumando los flujos tal cual. No tiene en cuenta que un peso "
                "de mañana vale menos que uno de hoy: para eso esta el descontado."
            ),
        ),
        Metrica(
            codigo="payback_descontado",
            nombre="Payback descontado",
            valor=pb_desc,
            unidad="anios",
            formula="Igual al simple, pero sobre los flujos traidos a valor presente",
            insumos=["inversion", "flujos", "tasa_descuento"],
            fuente=SESION6,
            criterio=(
                f"Se acepta si es menor a {plazo:g} años"
                if plazo is not None
                else "Sin plazo exigido definido"
            ),
            veredicto=veredicto_payback(pb_desc),
            lectura=(
                f"Descontando los flujos, la inversión se recupera en "
                f"{pb_desc:.2f} años."
                if pb_desc is not None
                else "La inversión no se recupera dentro del horizonte evaluado."
            ),
            ayuda=(
                "Los años para recuperar la inversión contando que la plata "
                "pierde valor con el tiempo. Mide riesgo y exigencia de "
                "liquidez. Su limitacion: ignora todo lo que pase después."
            ),
        ),
        Metrica(
            codigo="indice_rentabilidad",
            nombre="Índice de rentabilidad (IR)",
            valor=ir,
            unidad="veces",
            formula="IR = VP de los flujos futuros / Inversión inicial",
            insumos=["inversion", "flujos", "tasa_descuento"],
            fuente=SESION6,
            criterio="Crea valor si IR > 1",
            veredicto=(
                "sin_dato"
                if ir is None
                else "favorable" if ir > 1 else "limite" if ir == 1 else "desfavorable"
            ),
            lectura=(
                f"Cada peso invertido genera {ir:.2f} pesos de valor presente."
                if ir is not None
                else "No se puede calcular sin inversión inicial."
            ),
            ayuda=(
                "Cuánto valor presente produce cada peso invertido. Es el "
                "criterio para escoger entre proyectos cuando el presupuesto "
                "es limitado. No sirve para comparar proyectos de tamaños "
                "muy distintos."
            ),
        ),
    ]
    return metricas


# ================================================================== VEREDICTO


def evaluar_proyecto(proyecto: Proyecto) -> dict:
    """Evaluación completa: metricas, semaforo, escenarios y veredicto.

    El veredicto se construye de las metricas y no al reves. Igual que el
    puntaje de salud, tiene que poder discutirse renglon por renglon: si el
    profesor no esta de acuerdo con un criterio, discute ese criterio y no
    la conclusión entera.
    """
    metricas = _metricas(proyecto)
    por_codigo = {m.codigo: m for m in metricas}

    decisivas = ["vpn", "tir", "indice_rentabilidad", "payback_descontado"]
    favorables = sum(1 for c in decisivas if por_codigo[c].veredicto == "favorable")
    desfavorables = sum(1 for c in decisivas if por_codigo[c].veredicto == "desfavorable")

    vpn = por_codigo["vpn"].valor
    crea_valor = vpn is not None and vpn > 0

    if crea_valor and desfavorables == 0:
        semaforo, veredicto = "verde", "viable"
    elif crea_valor:
        semaforo, veredicto = "amarillo", "viable con reparos"
    else:
        semaforo, veredicto = "rojo", "no viable"

    reparos = [
        f"{por_codigo[c].nombre}: {por_codigo[c].criterio}"
        for c in decisivas
        if por_codigo[c].veredicto == "desfavorable"
    ]

    quiebre = punto_de_quiebre(proyecto)
    escenarios_calculados = escenarios(proyecto)
    resisten = sum(1 for e in escenarios_calculados if e["crea_valor"])

    if veredicto == "viable":
        recomendacion = (
            f"Se recomienda ejecutar el proyecto. {quiebre['lectura']}"
        )
    elif veredicto == "viable con reparos":
        detalle = reparos[0] if reparos else "hay criterios que no se cumplen"
        recomendacion = (
            f"El proyecto crea valor, pero no cumple todos los criterios: "
            f"{detalle}. Se recomienda presentarlo pidiendo flexibilizar esa "
            f"condición. {quiebre['lectura']}"
        )
    else:
        recomendacion = (
            f"No se recomienda ejecutar el proyecto con estos supuestos: no "
            f"alcanza a cubrir el costo de capital exigido. {quiebre['lectura']}"
        )

    return {
        "proyecto": {
            "nombre": proyecto.nombre,
            "inversion": proyecto.inversion,
            "flujos": proyecto.flujos,
            "tasa_descuento": proyecto.tasa_descuento,
            "plazo_exigido": proyecto.plazo_exigido,
            "horizonte": proyecto.horizonte,
            "moneda": proyecto.moneda,
            "unidad": proyecto.unidad,
        },
        "metricas": [vars(m) for m in metricas],
        "tabla_descuento": flujos_descontados(proyecto),
        "escenarios": escenarios_calculados,
        "escenarios_que_crean_valor": resisten,
        "punto_de_quiebre": quiebre,
        "semaforo": semaforo,
        "veredicto": veredicto,
        "criterios_favorables": favorables,
        "criterios_evaluados": len(decisivas),
        "reparos": reparos,
        "recomendacion": recomendacion,
    }
