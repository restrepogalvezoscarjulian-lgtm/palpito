# Estado — 9 de septiembre de 2026

## Dónde vamos

**Pálpito** es una aplicación de diagnóstico financiero construida para la
asignatura *Análisis y Gerencia Financiera* (Universidad El Bosque). Está
**terminada, con los tres huecos que quedaban ya cerrados**.

Verificado hoy, no de memoria:

- `157 passed` — la suite completa (el 29 de agosto eran 71)
- Commit `549787f` en `main`, **sin nada pendiente y sincronizado con GitHub**
- <https://github.com/restrepogalvezoscarjulian-lgtm/palpito> (MIT)

Lo que hace: valida la calidad de los estados financieros → calcula 26
indicadores con trazabilidad → dispara 11 reglas de alerta → **califica la salud
de 0 a 100 con la metodología a la vista** → **dibuja tres gráficas** → una IA
redacta el diagnóstico y responde preguntas. Y ahora **los datos entran desde un
archivo**: Excel, CSV o PDF, sin digitar.

---

## Lo primero al retomar

**No hay trabajo a medias.** Los tres huecos del estado anterior están cerrados:

| Hueco | Estado |
|---|---|
| Gráficas | ✅ sección 6 · márgenes, ciclo de caja y DuPont |
| Puntaje de salud 0-100 | ✅ sección 2 · `backend/motor/salud.py` |
| Cargar Excel / PDF | ✅ botón *Cargar archivo* · `backend/motor/importacion.py` |

**Para arrancar el servidor:**
```bash
cd palpito/backend
uvicorn api:app --reload      # → http://localhost:8000
python -m pytest -q           # deben pasar 157
```

🔴 **Lo que falta es probarlo con un archivo de verdad.** Toda la importación se
verificó con archivos generados en las pruebas, no con un estado financiero real
del profesor o de un cliente. Los formatos raros aparecen con archivos reales:
hojas con subtotales intercalados, cuentas partidas en dos renglones, PDF
escaneados. **Ese es el siguiente paso natural, y necesita un archivo suyo.**

---

## Lo que se decidió, y por qué

**La IA nunca calcula. Ahora con un matiz importante.**
Sigue siendo la decisión de arquitectura central: el motor (Python) calcula y
decide; el modelo recibe los números ya resueltos y solo los traduce a prosa.
**Lo nuevo:** en la importación el modelo también puede *proponer* a qué cuenta
corresponde una fila —clasificar un nombre, no un valor—. La regla quedó así:
**el modelo puede opinar sobre CÓMO SE LLAMA una fila, jamás sobre cuánto vale.**
Y esa propuesta nunca se aplica sola: llega marcada, con su nivel de confianza,
y el usuario confirma o corrige antes de que se calcule nada.

**El puntaje de salud se construyó para ser discutible renglón por renglón.**
Un score sin metodología es un número que hay que creer. Por eso:
`nota = 70% nivel + 30% tendencia`, y cada indicador se abre en pantalla
mostrando el umbral con el que se comparó, **por qué ese umbral**, la fuente
bibliográfica y la escala dibujada con una marca donde cayó la empresa. Si el
profesor discute un umbral, discute *ese* y no el puntaje entero.

**Las escalas castigan los dos extremos.** Una razón corriente de 5 no saca 100:
es capital ocioso. Un endeudamiento de cero tampoco: desaprovecha el
apalancamiento. Desarma la crítica fácil de "más siempre es mejor".

**Un dato faltante no vale cero.** Se excluye del puntaje, su peso se reparte
entre los demás y se reporta cuál se excluyó. Confundir *no informado* con
*malo* falsea la nota. Lo mismo en la importación: una celda vacía entra como
dato ausente, nunca como cero.

**Se documentó qué NO es el puntaje.** En `FORMULAS.md` sección 7.6: no es un
modelo de riesgo tipo Altman ni sirve para comparar empresas de sectores
distintos. Mejor decirlo antes de que lo pregunten.

**Las gráficas no calculan.** SVG escrito a mano, sin librerías ni CDN. El
navegador solo ubica en coordenadas números que ya resolvió el motor, y está
dicho en la leyenda de la sección. El eje siempre incluye el cero para que
ninguna barra exagere una diferencia.

**Se evitó PyMuPDF a propósito.** Es AGPL y contaminaría la licencia MIT del
proyecto. Se usa `pdfplumber` (MIT).

**Se calcula bien aunque la cartilla del curso esté mal.**
Cinco errores encontrados en el material (ROA invertido, GAF inconsistente,
datos que no cuadran en DuPont, precio inconsistente en punto de equilibrio,
signos invertidos). Están en `FORMULAS.md` sección 8 como *criterio adoptado*.
**Decisión de Oscar: se reportan, no se ocultan.**

**El caso base tiene el balance descuadrado y eso es una funcionalidad.**
Comercial Andina no cuadra por 550 (2023) y 390 (2024) millones. La app lo
detecta sola y reporta el endeudamiento por dos vías: informado (55,75%) e
implícito (61,43%). La diferencia *es* el diagnóstico. Y por eso su puntaje
—**58,9 sobre 100, frágil**— sale marcado como **no confiable**: la validación
sigue siendo puerta previa.

**Un solo contenedor, sin frameworks de frontend.** FastAPI calcula y sirve la
interfaz. HTML plano con JavaScript vanilla. Sin build, sin Node.

---

## Las trampas

🔴 **Un servidor viejo no conoce los endpoints nuevos.** Si `POST /api/importar`
responde **"Method Not Allowed"**, no está roto: es que `uvicorn` se arrancó sin
`--reload` antes de que existiera la ruta, y `StaticFiles` montado en `/` atrapa
la petición. **Se reinicia y ya.** Costó un rato de diagnóstico.

🔴 **Un año se lee como cifra.** `2023` en un encabezado es un número perfectamente
válido, así que la fila de títulos entraba como si fuera una cuenta. La regla
que quedó: una fila es encabezado solo si **todas** sus cifras son años.

🔴 **En PDF los nombres largos se parten.** "Efectivo y equivalentes 450 380"
perdía la palabra "equivalentes" al separar nombre de cifras con `rsplit`. Ahora
se corta por la **cola de números**, no por los últimos espacios.

🔴 **Al generar JavaScript desde scripts de Python, cuidado con `\n`.** Ya rompió
el frontend una vez. El método que funcionó esta sesión: escribir el fragmento
en un archivo aparte con la herramienta de escritura, y que el script de Python
**lo lea del archivo** en vez de llevarlo como literal. Nunca `"...\n..."` dentro
del script.

⚠️ **Los heredoc de bash se atragantan con JavaScript.** Un `cat > archivo <<'FIN'`
con backticks y plantillas dentro falló con *unexpected EOF*. Misma solución.

⚠️ **`reportlab` genera PDF sin bordes por defecto**, y sin líneas `pdfplumber` no
reconoce la tabla: cae a la vía de texto. Para probar la vía de tablas hay que
ponerle `TableStyle(GRID)` explícito. Ambas vías están probadas.

⚠️ **`jsdom` está instalado en la carpeta temporal, no en el proyecto.** Se usó
para probar la interfaz con un DOM real. Si se quiere repetir esa prueba, hay
que reinstalarlo; el proyecto sigue sin Node ni `package.json`, y así debe
quedarse.

⚠️ **`let` no cuelga del `window`.** Las variables del frontend declaradas con
`let` no son accesibles desde fuera, así que una prueba de interfaz debe leer
del DOM, no de la variable.

🔴 **El Dockerfile NUNCA se ha construido.** No hay Docker en el PC. La imagen se
armará por primera vez en el servidor. **Y ahora pesa más**: se agregaron
`openpyxl`, `pdfplumber` y `python-multipart` a `requirements.txt`.

🔴 **En Dokploy: usar tipo "Application", NO "Compose".** Los servicios Compose se
salen de `dokploy-network` en **cada** redespliegue y hay que reconectarlos a
mano. Los Application se unen solos.

🔴 **Rutas con `:` en Git Bash de Windows.** `git show origin/main:.env.example`
falla. Usar `MSYS_NO_PATHCONV=1` adelante.

**La clave de OpenRouter vive solo en `palpito/.env`**, que está en `.gitignore`.
Verificado: NO está en GitHub. Modelo actual: `deepseek/deepseek-v4-flash`
(~USD 0,00004 por diagnóstico).

---

## 🔴 Pendientes que son de Oscar, no míos

- **¿Cuándo desplegar en `finanzas.torbex.com.co`?** Todo está listo (DNS en
  Namecheap, guía en `docs/DESPLIEGUE.md`). Él decidió dejarlo en local. **Sigue
  sin respuesta desde el 29 de agosto.** No desplegar sin que lo pida.

- **¿Se le regala el repositorio al profesor, y cómo?** Ya está público con
  licencia MIT a su nombre, pero **no se ha definido cómo ni cuándo se entrega**.
  Sigue sin respuesta.

- **¿Qué exige la rúbrica de calificación?** Nunca se supo con qué lo califican
  ni cuál es el entregable formal. La app excede lo que pide el taller, pero
  convendría confirmar que no falta algo puntual. Sigue sin respuesta.

- **¿Tiene un estado financiero real para probar la importación?** Es lo único
  que le falta a la funcionalidad nueva. Un Excel o PDF de verdad —del curso, de
  Serviteca, del restaurante— destaparía los formatos raros que un archivo de
  prueba no tiene.

---

## Contexto que un chat nuevo no puede deducir

**Origen del nombre.** Capítulo 1 de Oscar León García, bibliografía del curso:
*"el logro del OBF se puede verificar a través de lo que se denominará **pálpito
del empresario** con respecto al comportamiento del flujo de caja"*. La app
convierte ese pálpito en números verificables. Está como epígrafe en la cabecera.

**De dónde salieron las funcionalidades.** Se estudiaron dos aplicaciones:
- *Syft Analytics* → el módulo de **calidad de datos** (su función "Review"),
  que resultó ser lo más valioso.
- *Fireflies.ai* → el patrón **"preguntar en lenguaje natural y citar la
  fuente"** (su función AskFred).

Lo demás es propio: la validación como puerta previa, el endeudamiento por
partida doble, el modo docente, el puente de caja de García, la arquitectura
"la IA no calcula", el editor de escenarios, el puntaje auditable y la
importación en dos etapas.

**Estructura del proyecto:**
```
palpito/
├── backend/motor/     modelos · validacion · indicadores · diagnostico
│                      · salud (puntaje 0-100) · importacion · narrativa
├── backend/tests/     157 pruebas
├── backend/api.py     FastAPI: calcula y sirve la interfaz
├── frontend/          index.html, sin frameworks (1.301 líneas)
├── casos/             comercial_andina.json
├── docs/DESPLIEGUE.md guía paso a paso para Dokploy
├── FORMULAS.md        fórmulas, fuentes, metodología del puntaje (§7)
│                      y los 5 errores de la cartilla (§8)
└── .env               🔴 la clave (NO se sube a git)
```
