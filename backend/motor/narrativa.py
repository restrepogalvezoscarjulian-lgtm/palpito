"""Capa de narrativa: la IA redacta, no calcula.

Principio de diseno de Palpito: el modelo de lenguaje NUNCA hace aritmetica ni
decide que esta mal. Recibe un contexto con los numeros ya calculados y
verificados por el motor, y su unico trabajo es traducirlos a lenguaje que un
empresario entienda.

Consecuencias practicas:
  - No puede inventar un indicador que no exista.
  - No puede equivocarse en una division.
  - Si el modelo no esta configurado, la aplicacion sigue funcionando completa;
    solo pierde el parrafo en prosa.
"""

from __future__ import annotations

import os

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
            "No hay clave de OpenRouter configurada. El analisis numerico funciona "
            "completo; solo falta la redaccion en prosa."
        ),
    }


# --------------------------------------------------------- armado del contexto

INSTRUCCIONES = """Eres un analista financiero senior que le explica a un empresario \
colombiano de pyme, sin formacion contable, que esta pasando en su empresa.

REGLAS ABSOLUTAS:
1. NO calcules nada. Todos los numeros que necesitas ya estan en el CONTEXTO.
2. NO menciones ninguna cifra que no aparezca literalmente en el CONTEXTO.
3. Si un dato dice "no disponible", di que no se puede saber y por que. Nunca lo estimes.
4. Si el CONTEXTO reporta problemas de calidad de los datos, adviertelo primero:
   un diagnostico sobre datos inconsistentes puede estar equivocado.
5. Escribe en espanol de Colombia, claro y directo. Usa analogias del dia a dia
   de un comerciante. Nada de jerga sin explicar.
6. Se honesto: si la empresa esta mal, dilo sin rodeos. No adornes.

FORMATO DE LA RESPUESTA (usa markdown, sin titulo principal):
**Qué está pasando** - dos o tres frases con el panorama general.
**Por qué** - la cadena causal: que empezo el problema y como se propago.
**Lo más urgente** - las tres cosas que hay que atender, en orden.

Maximo 400 palabras. Cada afirmacion debe apoyarse en un numero del CONTEXTO."""


def _fmt(v, unidad="", dec=2):
    if v is None:
        return "no disponible"
    if unidad == "%":
        return f"{v:,.2f}%"
    if unidad == "dias":
        return f"{v:,.1f} dias"
    if unidad == "monto":
        return f"{v:,.0f}"
    return f"{v:,.{dec}f}"


def construir_contexto(analisis: dict) -> str:
    """Serializa el analisis a texto plano para el modelo.

    Es deliberadamente exhaustivo: entre mas completo el contexto, menos
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
            "X-Title": "Palpito - Diagnostico Financiero",
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
    """Redacta el diagnostico en prosa a partir del analisis ya calculado."""
    if not disponible():
        return {"disponible": False, "texto": "", **estado()}
    contexto = construir_contexto(analisis)
    texto = _llamar([
        {"role": "system", "content": INSTRUCCIONES},
        {"role": "user", "content": f"CONTEXTO:\n{contexto}\n\nRedacta el diagnostico."},
    ])
    return {"disponible": True, "texto": texto, "modelo": modelo(), "motivo": ""}


INSTRUCCIONES_PREGUNTA = """Eres un analista financiero que responde preguntas de un \
empresario sobre SU PROPIA empresa, usando unicamente el CONTEXTO entregado.

REGLAS ABSOLUTAS:
1. NO calcules. Usa solo los numeros del CONTEXTO.
2. Si la pregunta no se puede responder con el CONTEXTO, dilo claramente y explica
   que dato haria falta. No inventes.
3. Termina SIEMPRE con una linea que empiece con "Fuentes:" listando las cifras
   exactas del CONTEXTO en las que te apoyaste, separadas por " · ".
4. Espanol de Colombia, directo, maximo 200 palabras antes de las fuentes."""


def responder(analisis: dict, pregunta: str) -> dict:
    """Responde una pregunta libre anclada a los datos de la empresa."""
    if not disponible():
        return {"disponible": False, "texto": "", **estado()}
    pregunta = (pregunta or "").strip()
    if not pregunta:
        raise ValueError("La pregunta esta vacia.")
    if len(pregunta) > 500:
        raise ValueError("La pregunta es demasiado larga (maximo 500 caracteres).")

    contexto = construir_contexto(analisis)
    texto = _llamar([
        {"role": "system", "content": INSTRUCCIONES_PREGUNTA},
        {"role": "user", "content": f"CONTEXTO:\n{contexto}\n\nPREGUNTA: {pregunta}"},
    ], max_tokens=700)
    return {"disponible": True, "texto": texto, "modelo": modelo(), "motivo": ""}
