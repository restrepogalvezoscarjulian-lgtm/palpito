# Estado — 10 de septiembre de 2026

## Dónde vamos

**Pálpito** es una aplicación de diagnóstico financiero para *Análisis y Gerencia
Financiera* (Universidad El Bosque). Está **terminada y funcionando**, con todo
lo que pidieron las dos clases grabadas ya implementado.

Verificado hoy, no de memoria:

- **`300 passed`** — la suite completa (el 29 de agosto eran 71; ayer en la
  mañana, 157)
- **17 rutas** vivas en la API · **11 módulos** en el motor
- 🔴 **32 archivos sin confirmar en git.** Todo el trabajo de ayer existe en un
  solo disco duro.
- <https://github.com/restrepogalvezoscarjulian-lgtm/palpito> (MIT)

Qué hace: valida la calidad de los estados financieros → calcula 28 indicadores
con trazabilidad → dispara 11 reglas de alerta → califica la salud de 0 a 100 →
compara contra el sector → **evalúa proyectos de inversión** → dibuja gráficas →
una IA redacta el diagnóstico y responde preguntas. Los datos entran a mano,
desde Excel, CSV o PDF.

---

## Lo primero al retomar

**1. 🔴 Confirmar el trabajo en git.** Es lo más urgente. Son 32 archivos, entre
ellos seis módulos y siete archivos de pruebas que solo existen aquí. Oscar no
ha pedido el commit todavía, así que **hay que preguntárselo, no hacerlo solo**.

**2. Para levantar la aplicación:**
```bash
cd palpito/backend
uvicorn api:app --reload      # → http://localhost:8000
python -m pytest -q           # deben pasar 300
```
⚠️ Los servidores que levanta el asistente **mueren al cerrarse su sesión**. El
día de la exposición hay que levantarlo desde una terminal propia.

**3. No hay trabajo a medias.** Todo lo empezado quedó cerrado y probado.

---

## Lo que se decidió, y por qué

Un chat nuevo no puede deducir esto leyendo el código.

**La IA nunca calcula.** Sigue siendo la decisión central. El motor calcula y
decide; el modelo recibe números ya resueltos y los traduce a prosa. Conexión:
OpenRouter, `deepseek/deepseek-v4-flash`, clave en `.env` (fuera de git). Hace
cuatro cosas: redacta el diagnóstico, responde preguntas, redacta el concepto de
viabilidad del proyecto, y propone a qué cuenta corresponde una etiqueta
desconocida. **El modelo puede opinar sobre cómo se llama una fila, jamás sobre
cuánto vale.**

**Detectar las páginas de los estados NO usa el modelo.** Oscar propuso que la
IA encontrara sola dónde está el balance. Se hizo determinista
(`motor/secciones.py`) porque un estado financiero siempre se anuncia con las
mismas palabras: buscarlas es instantáneo, gratis y **auditable** —el resultado
dice qué marcadores encontró y con qué puntaje—. Un modelo ahí cobraría, tardaría
y podría inventarse una página.

**Nada externo se inventa.** El WACC y las referencias sectoriales son datos que
no se deducen de los estados financieros. Si no se declaran, se reportan como no
disponibles. El benchmark **hereda** la dirección de mejora de `CRITERIOS` en
`salud.py` en vez de redefinirla, y una prueba fija esa igualdad: si el puntaje
dice que bajar el endeudamiento es mejorar, el benchmark no puede decir lo
contrario.

**La inversión de un proyecto viaja aparte de los flujos y positiva.** El motor
le pone el signo. Confundirlo es el error más común del tema, y el índice de
rentabilidad necesita distinguirlos para dividir uno por otro.

**Se reportan los dos paybacks, no uno.** La diferencia entre el simple y el
descontado *es* el hallazgo del taller.

**La TIR se resuelve por bisección.** Para más de dos periodos no hay fórmula
cerrada: es un polinomio.

**La dirección visual es un instrumento de registro de precisión** —retícula
milimetrada, escalas calibradas, agujas—. La eligió Oscar entre tres opciones.
Todo el sistema está en `DESIGN.md`, escrito desde lo construido.

**Dos calibraciones, y no son decorativas.** Oscura para pantalla y Teams; clara
de alto contraste para proyector, porque **un proyector de salón lava los
negros**. Botón al pie de la barra lateral.

**Las tildes importan.** El código se escribió sin ellas por convención y eso
llegaba a la pantalla ("La operacion no genero caja"). En una exposición se lee
como descuido.

---

## Lo verificado contra el profesor

Él resolvió el taller de la sesión 6 en voz alta, así que sus cifras sirven de
patrón:

| | Profesor | Pálpito |
|---|---|---|
| VP de los flujos | 1.706 | 1.705,8 ✅ |
| VPN | 206 | 205,8 ✅ |
| Payback descontado | 3,57 años | 3,57 ✅ |
| Índice de rentabilidad | 1,14 | 1,14 ✅ |
| **TIR** | **16,7%** | **15,63%** ❌ |

**La TIR del profesor está mal y se demuestra solo:** al 16,7% los flujos
descontados suman 1.465 contra una inversión de 1.500, o sea el VPN sería
negativo — pero él concluyó que era positivo. Queda en `FORMULAS.md §8.6` como
la **sexta** discrepancia con el material del curso. La conclusión no cambia
(sigue siendo viable por TIR); cambia la cifra.

---

## Las trampas

Lo que ya costó horas encontrar.

### De la importación de archivos reales

🔴 **Un PDF que "se lee bien" puede estar entregando basura.** Si el documento
trae índice y los estados van escaneados, se lee el índice y los números de
página entran como saldos. Revisar siempre los avisos antes de confirmar.

🔴 **El conteo de páginas escaneadas va sobre el documento COMPLETO**, aunque
solo se lean unas páginas. Al acotar el rango se rompió esto una vez y **el
aviso más importante desapareció** sin que nada fallara.

🔴 **`importacion.py` va sin tildes a propósito.** Su diccionario de sinónimos se
compara contra etiquetas ya normalizadas (el normalizador quita las tildes). Si
se le ponen tildes a las claves, deja de reconocer las cuentas.

🔴 **`unidad="dias"` y `unidad="anios"` son valores de enumeración**, no texto.
El frontend los compara y los traduce al mostrar. No acentuarlos.

⚠️ **Los estados publicados traen costos y gastos entre paréntesis** (negativos)
porque los están restando. Se voltean al armar, **nunca en silencio**: queda
anotado en `supuestos.ajustes_importacion`.

### Del código

🔴 **Reponer tildes con búsqueda y reemplazo ROMPE el código.** Con `\b` el guion
bajo protege `razon_corriente`, pero **nada protege a los identificadores sin
guion bajo**: `formula=` se volvió `fórmula=` y `motor.diagnostico` se acentuó.
La forma correcta: recorrer con `tokenize` y tocar **solo tokens STRING que
contengan un espacio** (un identificador nunca lleva espacios).

🔴 **Las f-strings de Python 3.12 no son tokens STRING.** Su texto viaja en
`FSTRING_MIDDLE`, y ahí vive buena parte de la prosa del motor.

🔴 **No le agregue periodos a `comercial_andina.json`.** Las pruebas verifican
por posición: meter un año al frente corre todos los índices y revientan 29. Los
casos nuevos van en archivos nuevos.

🔴 **Un servidor viejo no conoce el código nuevo.** Si algo responde raro después
de tocar el backend, es que `uvicorn` se arrancó sin `--reload`. Se reinicia y ya.

🔴 **Rutas con `:` en Git Bash de Windows.** `git show origin/main:archivo` falla.
Usar `MSYS_NO_PATHCONV=1` adelante.

### De la interfaz

⚠️ **Enmascarar un elemento desvanece también su texto.** La retícula del
dictamen borraba las letras hasta que se movió a un pseudo-elemento `::before`.

⚠️ **`button:hover:not(:disabled)` tiene más especificidad que `button.primario`**
y le robaba el color, dejando texto claro sobre ámbar (1,8:1, ilegible).

🔴 **Chrome headless en Windows tiene un ancho mínimo de ventana (~490px).** Una
captura pedida a 390px es una página de 490px recortada y **miente**: parece que
el texto se desborda cuando no. Para verificar responsivo hay que cargar la
página en un iframe del ancho buscado y comparar `scrollWidth` con `clientWidth`.

🔴 **Al generar JavaScript desde Python, cuidado con `\n`,** y los heredoc de
bash se atragantan con JavaScript. El método que funciona: escribir el fragmento
en un archivo aparte y que el script **lo lea del archivo**.

### Del despliegue

🔴 **El Dockerfile NUNCA se ha construido.** No hay Docker en el PC.

🔴 **En Dokploy: usar tipo "Application", NO "Compose".** Los Compose se salen de
`dokploy-network` en cada redespliegue.

---

## Los casos, y cuál no se toca

- **`comercial_andina.json`** — el del taller, dos periodos. 🔴 **NO MODIFICAR.**
  La suite lo verifica contra valores calculados a mano: es la evidencia de
  auditoría del proyecto.
- **`andina_trienio.json`** — el mismo caso con 2022 por delante. Las cifras de
  2022 son una extensión didáctica coherente con la historia, y conservan el
  balance descuadrado a propósito.
- **`andina_con_benchmark.json`** — el trienio con referencias sectoriales.
  🔴 **Esas cifras son ILUSTRATIVAS, no son datos reales del sector.** Está dicho
  en sus propios supuestos.

---

## Empresas grandes: qué se probó de verdad

**Ecopetrol 2024** (146 páginas): ❌ **no sirve ese PDF.** Las páginas 11-17 —los
estados— son **imágenes escaneadas** (hojas firmadas). Lo único legible es el
índice y las notas. La app ahora lo detecta y avisa dos veces.

**Nutresa 2025** (75 páginas): ✅ **funciona.** Texto en todas las páginas. Las
páginas se detectan solas (10-12), 17 cuentas, dos periodos. Verificado contra el
PDF: margen bruto 39,46%, razón corriente 1,97, días de inventario 75,0.

**La limitación que queda, y es de diseño:** el catálogo tiene **23 cuentas,
pensadas para una pyme**. Un holding tiene crédito mercantil, intangibles e
inversiones en asociadas que no caben. Por eso la validación reporta que el
activo total no cuadra con activo corriente + PPE. **No invalida el análisis**
—liquidez, márgenes, rotación y rentabilidad no dependen de esas cuentas— pero
conviene decirlo antes de que lo pregunten.

---

## 🔴 Pendientes que son de Oscar, no míos

- **¿Se confirma el trabajo en git?** 32 archivos sin subir. Es lo más urgente y
  no se hace sin su palabra.
- **¿Cuándo es la exposición?** El profesor dijo el 2 de septiembre que quedaban
  tres clases y que la última era la nota. **Ya tiene fecha real.**
- **¿Qué exige la rúbrica?** Sin respuesta desde el 29 de agosto. La app excede
  el taller, pero convendría confirmar que no falta algo puntual.
- **¿Se le entrega el repositorio al profesor, y cómo?** Sin definir.
- **¿Desplegar en `finanzas.torbex.com.co`?** Todo listo; él decidió dejarlo en
  local. No desplegar sin que lo pida.
- **¿Cargar un estado financiero suyo de verdad?** De Serviteca o del
  restaurante. Sería la prueba con datos propios, que aún no se ha hecho.

---

## Estructura

```
palpito/
├── backend/motor/     modelos · validacion · indicadores · diagnostico
│                      · salud · importacion · narrativa · proyectos
│                      · benchmark · secciones
├── backend/tests/     300 pruebas en 11 archivos
├── backend/api.py     FastAPI: 17 rutas, calcula y sirve la interfaz
├── frontend/          index.html, sin frameworks, 7 módulos
├── casos/             3 casos (ver arriba cuál no se toca)
├── docs/DESPLIEGUE.md guía para Dokploy
├── FORMULAS.md        §9 proyectos · §10 EVA · §11 benchmark
│                      §8 los 6 errores del material del curso
├── PRODUCT.md         qué es y para quién
├── DESIGN.md          el sistema visual, escrito desde lo construido
├── CRUCES-VISTOS.md   coincidencias entre fuentes independientes
└── .env               🔴 la clave (NO se sube a git)
```
