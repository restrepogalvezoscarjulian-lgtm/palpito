"""Capa de narrativa: la IA redacta, no calcula.

Principio de diseno de Palpito: el modelo de lenguaje NUNCA hace aritmetica ni
decide que esta mal. Recibe un contexto con los números ya calculados y
verificados por el motor, y su único trabajo es traducirlos a lenguaje que un
empresario entienda.

Consecuencias practicas:
  - No puede inventar un indicador que no exista.
  - No puede equivocarse en una division.
  - Si el modelo no esta configurado, la aplicacion sigue funcionando completa;
    solo pierde el parrafo en prosa.
"""

from __future__ import annotations

import json
import os
import re

import httpx

URL_OPENROUTER = "https://openrouter.ai/api/v1/chat/completions"
MODELO_POR_DEFECTO = "deepseek/deepseek-v4-flash"
TIEMPO_LIMITE = 60.0


# ------------------------------------------------------------ configuracion


def api_key() -> str:
    return os.getenv("OPENROUTER_API_KEY", "").strip()


def modelo() -> str:
    return os.getenv("OPENROUTER_MODELO", MODELO_POR_DEFECTO).strip() or MODELO_POR_DEFECTO


def disponible() -> bool:
    """La narrativa es opcional: sin clave, la app funciona igual."""
    return bool(api_key())


def estado() -> dict:
    return {
        "disponible": disponible(),
        "modelo": modelo() if disponible() else None,
        "motivo": "" if disponible() else (
            "No hay clave de OpenRouter configurada. El análisis numerico funciona "
            "completo; solo falta la redaccion en prosa."
        ),
    }


# --------------------------------------------------------- armado del contexto

INSTRUCCIONES = """Eres un analista financiero senior que le explica a un empresario \
colombiano de pyme, sin formacion contable, que esta pasando en su empresa.

REGLAS ABSOLUTAS:
1. NO calcules nada. Todos los números que necesitas ya están en el CONTEXTO.
2. NO menciones ninguna cifra que no aparezca literalmente en el CONTEXTO.
3. Si un dato dice "no disponible", di que no se puede saber y por que. Nunca lo estimes.
4. Si el CONTEXTO reporta problemas de calidad de los datos, adviertelo primero:
   un diagnóstico sobre datos inconsistentes puede estar equivocado.
5. Escribe en español de Colombia, claro y directo. Usa analogias del día a día
   de un comerciante. Nada de jerga sin explicar.
6. Se honesto: si la empresa esta mal, dilo sin rodeos. No adornes.

FORMATO DE LA RESPUESTA (usa markdown, sin titulo principal):
**Qué está pasando** - dos o tres frases con el panorama general.
**Por qué** - la cadena causal: que empezo el problema y como se propago.
**Lo más urgente** - las tres cosas que hay que atender, en orden.

Máximo 400 palabras. Cada afirmacion debe apoyarse en un número del CONTEXTO."""


def _fmt(v, unidad="", dec=2):
    if v is None:
        return "no disponible"
    if unidad == "%":
        return f"{v:,.2f}%"
    if unidad == "dias":
        return f"{v:,.1f} días"
    if unidad == "monto":
        return f"{v:,.0f}"
    return f"{v:,.{dec}f}"


def construir_contexto(analisis: dict) -> str:
    """Serializa el análisis a texto plano para el modelo.

    Es deliberadamente exhaustivo: entre más completo el contexto, menos
    tentacion tiene el modelo de rellenar huecos por su cuenta.
    """
    L: list[str] = []
    per = analisis["periodos"]
    L.append(f"EMPRESA: {analisis['empresa']}")
    L.append(f"PERIODOS: {' y '.join(per)}")
    L.append(f"CIFRAS EN: {analisis['moneda']} ({analisis['unidad']})")

    # calidad de datos
    v = analisis["validacion"]
    L.append(f"\n== CALIDAD DE LOS DATOS: semaforo {v['semaforo'].upper()} ==")
    for h in v["hallazgos"]:
        L.append(f"- [{h['severidad']}] {h['mensaje']}")

    # puntaje de salud: ya viene calculado, el modelo solo puede citarlo
    s = analisis.get("salud") or {}
    if s.get("disponible"):
        L.append(f"\n== PUNTAJE DE SALUD FINANCIERA: {s['puntaje']:.1f} de 100 "
                 f"({s['banda']['nombre']}) ==")
        L.append(f"Metodología: {s['metodologia']['formula']}")
        for d in s["dimensiones"]:
            if d["evaluable"]:
                L.append(f"{d['nombre']} (peso {d['peso']:.0f}%): "
                         f"{d['puntaje']:.1f} de 100")
        if not s["confiable"]:
            L.append(f"ADVERTENCIA: {s['advertencia']}")

    # indicadores
    L.append("\n== INDICADORES CALCULADOS ==")
    categoria = None
    for i in analisis["indicadores"]:
        if i["categoria"] != categoria:
            categoria = i["categoria"]
            L.append(f"\n-- {categoria} --")
        vals = " -> ".join(_fmt(x, i["unidad"]) for x in i["valores"])
        L.append(f"{i['nombre']}: {vals}")

    # variaciones
    L.append("\n== VARIACION ENTRE PERIODOS (%) ==")
    for grupo in ("resultados", "balance"):
        for k, f in analisis["horizontal"][grupo].items():
            if f["variacion_relativa"] is not None:
                L.append(f"{k}: {f['variacion_relativa']:+.2f}%")

    # dupont
    d = analisis["dupont"].get("variacion_por_factor_pct")
    if d:
        L.append("\n== DUPONT: variacion de cada factor (%) ==")
        for k, val in d.items():
            if val is not None:
                L.append(f"{k}: {val:+.2f}%")

    # puente de caja
    p = analisis["puente_caja"]
    if p.get("disponible"):
        L.append("\n== PUENTE DE CAJA ==")
        L.append(f"UODI generada: {_fmt(p['uodi'], 'monto')}")
        L.append(f"Consumido por aumento del KTNO: -{_fmt(p['aumento_ktno'], 'monto')}")
        L.append(f"Consumido por activos fijos: -{_fmt(p['aumento_activos_fijos_neto'], 'monto')}")
        L.append(f"Flujo de caja libre aproximado: {_fmt(p['flujo_caja_libre_aprox'], 'monto')}")
        L.append(f"Variacion de la deuda financiera: {_fmt(p['variacion_deuda_financiera'], 'monto')}")
        L.append(f"Variacion del efectivo: {_fmt(p['variacion_efectivo'], 'monto')}")
        if p.get("es_aproximacion"):
            L.append(f"ADVERTENCIA: {p['advertencia']}")

    # alertas del motor de reglas
    L.append("\n== ALERTAS DETECTADAS POR EL MOTOR DE REGLAS (ya priorizadas) ==")
    for a in analisis["alertas"]:
        L.append(f"{a['prioridad']}. {a['titulo']}")
        for e in a["evidencia"]:
            L.append(f"   evidencia: {e}")

    return "\n".join(L)


# ------------------------------------------------------------------ llamadas


def _llamar(mensajes: list[dict], max_tokens: int = 1200) -> str:
    """Llama a OpenRouter. La clave nunca sale del servidor."""
    clave = api_key()
    if not clave:
        raise RuntimeError("No hay OPENROUTER_API_KEY configurada.")

    respuesta = httpx.post(
        URL_OPENROUTER,
        timeout=TIEMPO_LIMITE,
        headers={
            "Authorization": f"Bearer {clave}",
            "Content-Type": "application/json",
            "X-Title": "Palpito - Diagnóstico Financiero",
        },
        json={
            "model": modelo(),
            "messages": mensajes,
            "temperature": 0.2,   # bajo: queremos consistencia, no creatividad
            "max_tokens": max_tokens,
        },
    )
    if respuesta.status_code != 200:
        raise RuntimeError(
            f"OpenRouter respondio {respuesta.status_code}: {respuesta.text[:300]}"
        )
    datos = respuesta.json()
    try:
        return datos["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Respuesta inesperada de OpenRouter: {datos}") from exc


def narrar(analisis: dict) -> dict:
    """Redacta el diagnóstico en prosa a partir del análisis ya calculado."""
    if not disponible():
        return {"disponible": False, "texto": "", **estado()}
    contexto = construir_contexto(analisis)
    texto = _llamar([
        {"role": "system", "content": INSTRUCCIONES},
        {"role": "user", "content": f"CONTEXTO:\n{contexto}\n\nRedacta el diagnóstico."},
    ])
    return {"disponible": True, "texto": texto, "modelo": modelo(), "motivo": ""}


INSTRUCCIONES_PREGUNTA = """Eres un analista financiero que responde preguntas de un \
empresario sobre SU PROPIA empresa, usando únicamente el CONTEXTO entregado.

REGLAS ABSOLUTAS:
1. NO calcules. Usa solo los números del CONTEXTO.
2. Si la pregunta no se puede responder con el CONTEXTO, dilo claramente y explica
   que dato haria falta. No inventes.
3. Termina SIEMPRE con una línea que empiece con "Fuentes:" listando las cifras
   exactas del CONTEXTO en las que te apoyaste, separadas por " · ".
4. Español de Colombia, directo, máximo 200 palabras antes de las fuentes."""


def responder(analisis: dict, pregunta: str) -> dict:
    """Responde una pregunta libre anclada a los datos de la empresa."""
    if not disponible():
        return {"disponible": False, "texto": "", **estado()}
    pregunta = (pregunta or "").strip()
    if not pregunta:
        raise ValueError("La pregunta esta vacia.")
    if len(pregunta) > 500:
        raise ValueError("La pregunta es demasiado larga (máximo 500 caracteres).")

    contexto = construir_contexto(analisis)
    texto = _llamar([
        {"role": "system", "content": INSTRUCCIONES_PREGUNTA},
        {"role": "user", "content": f"CONTEXTO:\n{contexto}\n\nPREGUNTA: {pregunta}"},
    ], max_tokens=700)
    return {"disponible": True, "texto": texto, "modelo": modelo(), "motivo": ""}


# --------------------------------------------------- propuesta de cuentas

INSTRUCCIONES_CUENTAS = """Eres un asistente contable. Recibes etiquetas de filas de un
estado financiero y las relacionas con una lista cerrada de codigos de cuenta.

REGLAS ESTRICTAS:
1. Solo puedes usar codigos de la lista que te dan. Nada inventado.
2. Si una etiqueta no corresponde con claridad a ningun codigo, responde null.
   Dejarla sin asignar es la respuesta correcta y esperada muchas veces.
3. Nunca opines sobre los valores ni los interpretes: solo clasificas nombres.
4. Un codigo no puede usarse dos veces.
5. Responde ÚNICAMENTE un objeto JSON, sin texto alrededor y sin ```:
   {"asignaciones": [{"etiqueta": "...", "cuenta": "codigo o null", "confianza": "alta|media|baja"}]}

Confianza alta: la etiqueta es un sinonimo claro. Media: encaja pero con
ambiguedad. Baja: es una conjetura. Ante la duda, baja o null."""


def proponer_cuentas(etiquetas: list[str], disponibles: list[str]) -> dict:
    """Le pide al modelo que proponga a que cuenta corresponde cada etiqueta.

    Es lo único que el modelo hace en la importación, y es clasificación de
    texto, no cálculo: mira COMO SE LLAMA una fila, nunca cuánto vale. La
    propuesta llega marcada como tal y no se aplica sola: el usuario la
    confirma o la corrige en pantalla antes de que se calcule nada.
    """
    if not disponible():
        return {"disponible": False, "asignaciones": [], **estado()}
    etiquetas = [str(e).strip() for e in (etiquetas or []) if str(e).strip()][:60]
    if not etiquetas:
        return {"disponible": True, "asignaciones": [], "modelo": modelo(), "motivo": ""}

    peticion = (
        "CODIGOS DISPONIBLES (no uses ningun otro):\n"
        + "\n".join(f"- {c}" for c in disponibles)
        + "\n\nETIQUETAS A CLASIFICAR:\n"
        + "\n".join(f"- {e}" for e in etiquetas)
    )
    crudo = _llamar([
        {"role": "system", "content": INSTRUCCIONES_CUENTAS},
        {"role": "user", "content": peticion},
    ], max_tokens=900)

    asignaciones = _leer_json_asignaciones(crudo, etiquetas, disponibles)
    return {"disponible": True, "asignaciones": asignaciones,
            "modelo": modelo(), "motivo": ""}


def _leer_json_asignaciones(crudo: str, etiquetas: list[str],
                            disponibles: list[str]) -> list[dict]:
    """Lee la respuesta del modelo y descarta todo lo que no cuadre.

    El modelo puede devolver un codigo que no existe, repetir uno o inventarse
    una etiqueta que nadie le paso. Nada de eso puede llegar a la pantalla, así
    que se filtra aquí: lo que no calza se ignora en silencio y esa fila
    simplemente queda sin propuesta.
    """
    texto = (crudo or "").strip()
    if texto.startswith("```"):
        texto = re.sub(r"^```[a-z]*\s*|\s*```$", "", texto, flags=re.S)
    inicio, fin = texto.find("{"), texto.rfind("}")
    if inicio < 0 or fin <= inicio:
        return []
    try:
        datos = json.loads(texto[inicio:fin + 1])
    except (json.JSONDecodeError, ValueError):
        return []

    validas, usadas = [], set()
    conocidas = {e.strip().lower(): e for e in etiquetas}
    for item in datos.get("asignaciones") or []:
        if not isinstance(item, dict):
            continue
        etiqueta = conocidas.get(str(item.get("etiqueta", "")).strip().lower())
        cuenta = item.get("cuenta")
        if not etiqueta or not cuenta or cuenta not in disponibles or cuenta in usadas:
            continue
        confianza = str(item.get("confianza", "baja")).lower()
        if confianza not in ("alta", "media", "baja"):
            confianza = "baja"
        usadas.add(cuenta)
        validas.append({"etiqueta": etiqueta, "cuenta": cuenta, "confianza": confianza})
    return validas


# ------------------------------------------------- concepto de viabilidad

INSTRUCCIONES_PROYECTO = """Eres un analista financiero que le presenta a una junta \
directiva el concepto de viabilidad de un proyecto de inversión.

REGLAS ABSOLUTAS:
1. NO calcules nada. Todos los números ya están en el CONTEXTO.
2. El veredicto ya viene decidido en el CONTEXTO. NO lo contradigas ni lo suavices:
   tu trabajo es explicarlo, no volver a juzgar el proyecto.
3. NO menciones ninguna cifra que no aparezca literalmente en el CONTEXTO.
4. Si hay reparos, nombralos explicitamente. Una junta que aprueba sin conocer
   los reparos fue mal asesorada.
5. Español de Colombia, directo. Explica que significa cada indicador en plata
   real, no en jerga.

FORMATO (markdown, sin titulo principal):
**El concepto** - viable o no, y por que, en dos o tres frases.
**Lo que dicen los números** - VPN, TIR, payback e índice de rentabilidad leidos
en lenguaje de negocio.
**El riesgo** - cuánto aguanta el proyecto antes de dejar de crear valor.
**La recomendacion a la junta** - que debería decidirse, incluidas las condiciones
que habría que flexibilizar.

Máximo 350 palabras."""


def contexto_proyecto(evaluacion: dict) -> str:
    """Serializa la evaluación de un proyecto a texto plano para el modelo.

    Igual que construir_contexto: existe por transparencia, para poder auditar
    que el modelo no recibe nada que el motor no haya calculado antes.
    """
    p = evaluacion["proyecto"]
    lineas = [
        f"PROYECTO: {p['nombre']}",
        f"Inversión inicial: {_fmt(p['inversion'], 'monto')} {p['unidad']} de {p['moneda']}",
        f"Horizonte: {p['horizonte']} periodos",
        f"Tasa de descuento exigida (WACC): {_fmt(p['tasa_descuento'] * 100, '%')}",
    ]
    if p.get("plazo_exigido") is not None:
        lineas.append(f"Plazo máximo exigido para recuperar: {p['plazo_exigido']:g} años")
    lineas.append(
        "Flujos de caja proyectados: "
        + " · ".join(f"año {i + 1}: {_fmt(f, 'monto')}" for i, f in enumerate(p["flujos"]))
    )

    lineas.append("\nINDICADORES DEL PROYECTO:")
    for m in evaluacion["metricas"]:
        if m["valor"] is None:
            lineas.append(f"- {m['nombre']}: no disponible")
            continue
        if m["unidad"] == "porcentaje":
            valor = _fmt(m["valor"] * 100, "%")
        elif m["unidad"] == "anios":
            valor = f"{m['valor']:,.2f} años"
        elif m["unidad"] == "veces":
            valor = _fmt(m["valor"])
        else:
            valor = _fmt(m["valor"], "monto")
        lineas.append(
            f"- {m['nombre']}: {valor} | criterio: {m['criterio']} | "
            f"resultado: {m['veredicto']} | {m['lectura']}"
        )

    quiebre = evaluacion["punto_de_quiebre"]
    lineas.append(f"\nRIESGO: {quiebre['lectura']}")

    lineas.append("ESCENARIOS:")
    for e in evaluacion["escenarios"]:
        lineas.append(
            f"- {e['nombre']} (flujos {e['variacion_flujos'] * 100:+.0f}%): "
            f"VPN {_fmt(e['vpn'], 'monto')}, "
            f"{'crea valor' if e['crea_valor'] else 'destruye valor'}"
        )
    lineas.append(
        f"Escenarios que crean valor: {evaluacion['escenarios_que_crean_valor']} de "
        f"{len(evaluacion['escenarios'])}"
    )

    lineas.append(
        f"\nVEREDICTO DEL MOTOR: {evaluacion['veredicto'].upper()} "
        f"(semaforo {evaluacion['semaforo']}), "
        f"{evaluacion['criterios_favorables']} de {evaluacion['criterios_evaluados']} "
        f"criterios decisivos cumplidos"
    )
    if evaluacion["reparos"]:
        lineas.append("REPAROS: " + " · ".join(evaluacion["reparos"]))
    lineas.append(f"RECOMENDACION DEL MOTOR: {evaluacion['recomendacion']}")

    return "\n".join(lineas)


def narrar_proyecto(evaluacion: dict) -> dict:
    """Redacta el concepto de viabilidad sobre una evaluación ya calculada."""
    if not disponible():
        return {"disponible": False, "texto": "", "evaluacion": evaluacion, **estado()}
    contexto = contexto_proyecto(evaluacion)
    texto = _llamar([
        {"role": "system", "content": INSTRUCCIONES_PROYECTO},
        {"role": "user", "content": f"CONTEXTO:\n{contexto}\n\nRedacta el concepto."},
    ])
    return {
        "disponible": True,
        "texto": texto,
        "modelo": modelo(),
        "motivo": "",
        "evaluacion": evaluacion,
    }
