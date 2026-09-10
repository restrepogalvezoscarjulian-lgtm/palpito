# Estado — 10 de septiembre de 2026 (tercera jornada del día)

## Dónde vamos

**Pálpito** es una aplicación de diagnóstico financiero para *Análisis y Gerencia
Financiera* (Universidad El Bosque). Hoy pasó de "funciona con el caso del
taller" a **leer informes anuales reales de empresas colombianas**.

Verificado ahora, no de memoria:

- **`393 passed`** — la suite completa (el día empezó en 300)
- **Almacenes Éxito entra limpio**: 0 errores de calidad, margen bruto 25,3 %,
  días de inventario 63, cartera 11 días, endeudamiento 54 %. Cifras de un
  supermercado de verdad.
- 🔴 **HAY TRABAJO SIN COMMIT.** 6 archivos modificados. El último commit es
  `14253e5`; todo lo posterior existe en un solo disco duro.
- <https://github.com/restrepogalvezoscarjulian-lgtm/palpito> (MIT). Lo
  comprometido sí está subido: `main...origin/main` sin nada por delante.

---

## Lo primero al retomar

### 1. 🔴 Borrar dos archivos que dejaron mis pruebas en `casos/`

**Sigue pendiente: lo tiene que hacer Oscar.** Al asistente le bloquearon el
borrado de archivos.

```powershell
cd "C:\Users\Lenovo\Documents\UNIVERSIDAD\PERIODO 2026_4\ANALISIS Y GERENCIA FINACIERA\palpito"
Remove-Item "casos\comercial_andina_s_a_con_benchmark_de_ejemplo.json"
Remove-Item "casos\grupo_bolivar.json"
```

⚠️ **Corrección al ESTADO anterior, que decía que el primero era un duplicado.**
No lo es: es peor. Lleva el **nombre y los periodos de Comercial Andina** pero
por dentro tiene las **cifras reales de Éxito** (ventas 21.880.509). Es decir,
en el desplegable se ofrece como el caso del taller y muestra los números de un
supermercado. Salió del defecto de la casilla "Añadir estos años" que se arregló
el 10-sep (ver abajo). **Los tres del taller están intactos** (verificado
comparando campo por campo).

### 2. ✅ Resuelto — lo que quedó a medias ya se probó en el navegador

Verificado el 10-sep contra el servidor real, con `exito 2024.pdf` y
`exito 2025.pdf` subidos **a la vez**:

- Cola de varios archivos: revisa uno por uno y queda **2023-2024-2025** ✅
- "Guardar este caso": queda en disco con los tres periodos ✅
- "Borrar": aparece solo en casos propios, y borra ✅
- Los del taller están protegidos **por partida doble**: el botón no aparece y
  el servidor responde **403** si se pide la ruta a mano ✅

**Y destapó dos defectos, ya arreglados:**

1. 🔴 **La casilla "Añadir estos años" venía marcada también en el PRIMER
   archivo de la tanda**, contra lo que decía su propio comentario. Efecto: el
   primer archivo se fundía con **el caso que estuviera en pantalla** —al abrir
   la app, el del taller—. Es el origen del JSON corrupto del punto 1. Ahora hay
   `posicionEnTanda` y solo se marca del segundo en adelante.
2. "Quedan 1 archivo por revisar" → concuerda en singular.

⚠️ **Trampa nueva, y cara:** el navegador **reusa el `index.html` de la carga
anterior**. La prueba corrió dos veces dando el resultado viejo idéntico, sin
que nada fallara. En el guion de DevTools hay que mandar
`Network.setCacheDisabled {cacheDisabled:true}` antes de navegar.

⚠️ Al cargar los PDFs, la empresa queda con el **nombre del archivo**
("exito 2024"). Se corrige a mano en el campo *Empresa* de la revisión, pero
**hay que acordarse antes de la exposición**.

### 3. Hacer commit

**Preguntarle a Oscar antes de hacer push.**

---

## Lo que se arregló hoy (tercera jornada)

Oscar diagnosticó el problema él mismo: *"no son los estados, es los datos que el
modelo elige como predeterminados"*. Tenía razón, y las cifras lo confirman.

| | Antes | Ahora |
|---|---|---|
| Errores en Éxito 2024 | **10** | **0** |
| `ventas` | 60.481 (un renglón de derivados) | **21.880.509** ✅ |
| `pasivo_total` | no existía en el catálogo | **9.539.043** ✅ |
| Días de inventario | 3.614 (diez años) | **62,9** ✅ |

**Cuatro causas, todas nuestras:**

1. **Faltaban dos cuentas en el catálogo del importador.** `pasivo_total` y
   `pasivo_no_corriente` existen en `modelos.py` desde siempre, pero el
   importador no podía producirlas, así que **ningún balance real cuadraba**.
   El "Total pasivo" de Éxito estaba en el PDF sin asignar: con el patrimonio da
   exactamente el activo total.
2. **Renglones del flujo de efectivo se disfrazaban de resultados.**
   *(`CRUCES-VISTOS.md §9`.)*
3. **El diccionario elegía por frase más larga, no por posición.** Ahora manda lo
   que aparece **antes** en la etiqueta: `"TOTAL PASIVOS CORRIENTES Pasivos no
   corrientes"` trae el saldo del corriente, y lo de atrás es el encabezado
   pegado.
4. **Un error que no era un error.** *(`CRUCES-VISTOS.md §10`.)*

**Y de la jornada anterior**, ya comprometido: la vista previa que mostraba el
número de nota como saldo, el verde falso de Grupo Bolívar, unir años de varios
archivos, y el botón de guardar.

---

## Lo que se decidió, y por qué

Un chat nuevo no puede deducir esto leyendo el código.

### Decidido hoy

**El detector agrupa bloques y elige la pareja vecina**, no el mejor de cada
clase. Los estados financieros van seguidos: esa creencia ya estaba en el código
(`MAX_SEPARACION`), pero se aplicaba tarde, para descartar, en vez de temprano,
para elegir.

**La utilidad neta es la de operaciones continuadas**, y queda anotado con la
cifra que se dejó fuera.

**La empresa cargada entra a la lista de la sesión, y AHORA además se puede
guardar en disco** con el botón *"Guardar este caso"*, y borrar con *"Borrar"*.
Se mantiene la separación que se decidió: **probar un PDF no ensucia la carpeta;
guardar es un acto explícito**. Los tres casos del taller están protegidos en el
servidor: no se pueden pisar ni borrar, ni pidiéndolo.

**Se subió a GitHub**, después de dos días de commits solo locales. Oscar lo
pidió cuando se le dijo que 1.113 líneas vivían en un solo disco duro. ⚠️ Esto
**no** convierte el push en automático: **sigue sin subirse sin que lo pida.**

### Decisiones de fondo, que siguen vigentes

**La IA nunca calcula.** Sigue siendo la decisión central. El motor calcula y
decide; el modelo recibe números ya resueltos y los traduce a prosa. Conexión:
OpenRouter, `deepseek/deepseek-v4-flash`, clave en `.env` (fuera de git). Hace
cuatro cosas: redacta el diagnóstico, responde preguntas, redacta el concepto de
viabilidad del proyecto, y propone a qué cuenta corresponde una etiqueta
desconocida. **El modelo puede opinar sobre cómo se llama una fila, jamás sobre
cuánto vale.**

**Detectar las páginas de los estados NO usa el modelo.** Se hizo determinista
porque un estado financiero siempre se anuncia con las mismas palabras: buscarlas
es instantáneo, gratis y **auditable**. Que el detector se haya equivocado no
cambia la decisión: el arreglo fue mejor lógica, no un modelo.

**Nada externo se inventa.** El WACC y las referencias sectoriales no se deducen
de los estados. Si no se declaran, se reportan como no disponibles. El benchmark
**hereda** la dirección de mejora de `CRITERIOS` en `salud.py`.

**La inversión de un proyecto viaja aparte de los flujos y positiva.** El motor
le pone el signo. Es el error más común del tema.

**Se reportan los dos paybacks, no uno.** La diferencia entre el simple y el
descontado *es* el hallazgo del taller.

**La TIR se resuelve por bisección.** Para más de dos periodos no hay fórmula
cerrada: es un polinomio.

**La dirección visual es un instrumento de registro de precisión.** La eligió
Oscar entre tres opciones. Todo el sistema está en `DESIGN.md`.

**Dos calibraciones, y no son decorativas.** Oscura para pantalla y Teams; clara
de alto contraste para proyector, porque **un proyector de salón lava los negros**.

**Las tildes importan.** En una exposición, "La operacion no genero caja" se lee
como descuido. ⚠️ Con un matiz que hoy quedó fijado en pruebas: `importacion.py`
va sin tildes **solo en las claves del diccionario**; la prosa que ve el usuario
las lleva.

---

## Lo verificado contra el profesor

Él resolvió el taller de la sesión 6 en voz alta, así que sus cifras sirven de
patrón. Verificado hoy contra el API, no de memoria:

| | Profesor | Pálpito |
|---|---|---|
| VP de los flujos | 1.706 | 1.705,76 ✅ |
| VPN | 206 | 205,76 ✅ |
| Payback descontado | 3,57 años | 3,57 ✅ |
| Índice de rentabilidad | 1,14 | 1,14 ✅ |
| **TIR** | **16,7 %** | **15,62 %** ❌ |

**La TIR del profesor está mal y se demuestra solo.** Comprobado a mano hoy: a
15,62 % el VPN da **0,000**; a 16,7 % da **−35,17**. La TIR es, por definición, la
tasa a la que el VPN vale cero. Queda en `FORMULAS.md §8.6` como la **sexta**
discrepancia con el material del curso. La conclusión no cambia (sigue siendo
viable por TIR); cambia la cifra.

⚠️ **Corrección al ESTADO anterior**, que decía 15,63 %: a esa tasa el VPN da
−0,43, no cero. La cifra correcta es **15,62 %**.

---

## Las trampas

Lo que ya costó horas encontrar.

### De la importación de archivos reales

🔴 **Un PDF que "se lee bien" puede estar entregando basura.** Si el documento
trae índice y los estados van escaneados, se lee el índice y los números de
página entran como saldos. Revisar siempre los avisos antes de confirmar.

🔴 **El conteo de páginas escaneadas va sobre el documento COMPLETO**, aunque solo
se lean unas páginas. Al acotar el rango se rompió esto una vez y **el aviso más
importante desapareció** sin que nada fallara.

🔴 **Una nota del fondo del documento puede puntuar más que el estado de verdad.**
En Argos, una nota de la página 82 le ganaba al balance repartido en tres hojas.
Por eso el detector agrupa bloques. *(`CRUCES-VISTOS.md §4`.)*

🔴 **Leer una página de más puede cambiar una cifra sin avisar.** La 20 de Argos
subía la utilidad neta de 733.427 a 4.346.462, y de paso metía "OTRO RESULTADO
INTEGRAL" como gasto de renta. Hoy está protegido, pero la lección queda: el
rango de páginas no es un detalle de rendimiento, **es un dato de entrada**.

🔴 **El lector de PDF pega el total con el encabezado siguiente.** Produce
renglones como `"total pasivos corrientes pasivos no corrientes"`, donde las dos
cosas conviven. Por eso el corte mira **de qué es el total**, con un `.*?`
perezoso, no si la palabra "no" aparece por ahí.

🔴 **El archivo trae los TRES estados, y los del flujo de efectivo se disfrazan.**
"Compras de propiedades, planta y equipo" entraba como compras de mercancía y
disparaba los días de inventario a 3.614. Los verbos delatan: *compras de*,
*adiciones*, *adquisición*, *venta de*, *antes de cambios en*.
*(`CRUCES-VISTOS.md §9`.)*

🔴 **El diccionario elige por POSICIÓN, no por frase más larga.** El lector de PDF
pega el encabezado siguiente al total anterior. Una etiqueta dice lo que dice por
como **empieza**; lo de atrás es ruido.

🔴 **Los plurales van explícitos en el diccionario.** Sin `"total pasivos
corrientes"`, ese renglón empieza igual que `"total pasivos"` y se lo lleva el
pasivo TOTAL, que es otra cifra.

🔴 **`importacion.py` va sin tildes SOLO en las claves del diccionario.** Se
comparan contra etiquetas ya normalizadas (el normalizador quita las tildes). Los
avisos que lee el usuario **sí las llevan**. Dos pruebas fijan las dos mitades.

🔴 **`unidad="dias"` y `unidad="anios"` son valores de enumeración**, no texto. El
frontend los compara y los traduce al mostrar. No acentuarlos.

🔴 **La columna "Nota" se descarta por POSICIÓN, no por entenderla.** El armador se
queda con los dos últimos números porque hay dos periodos. Con tres periodos
declarados y columna de nota, volvería a fallar. *(`CRUCES-VISTOS.md §1`.)*

⚠️ **Los estados publicados traen costos y gastos entre paréntesis** (negativos)
porque los están restando. Se voltean al armar, **nunca en silencio**: y desde hoy
eso es cierto de verdad, no solo en un comentario. *(`CRUCES-VISTOS.md §7`.)*

### Del código

🔴 **`totales?` no significa "total" u "opcionalmente totales".** El `?` aplica
solo a la letra anterior: `totales?` es "totale" más una "s" opcional, y **no
empata con "total"**. Costó una depuración entera. Lo correcto es
`total(?:es)?`.

🔴 **Reponer tildes con búsqueda y reemplazo ROMPE el código.** Con `\b` el guion
bajo protege `razon_corriente`, pero **nada protege a los identificadores sin
guion bajo**: `formula=` se volvió `fórmula=`. La forma correcta: recorrer con
`tokenize` y tocar **solo tokens STRING que contengan un espacio**.

🔴 **Las f-strings de Python 3.12 no son tokens STRING.** Su texto viaja en
`FSTRING_MIDDLE`, y ahí vive buena parte de la prosa del motor.

🔴 **No le agregue periodos a `comercial_andina.json`.** Las pruebas verifican por
posición: meter un año al frente corre todos los índices y revientan 29. Los
casos nuevos van en archivos nuevos.

🔴 **`validacion.validar()` recibe un `EstadosFinancieros`, no un dict.** Hay que
envolverlo: `EstadosFinancieros(est)`.

🔴 **`Tabla.como_dict()`, no `a_dict()`.** Y las `Fila` son dataclasses, no
diccionarios: se lee `f.cuenta`, no `f.get("cuenta")`.

🔴 **Para el análisis completo hay atajo:** `api._analizar(ef)` encadena
validación, indicadores, alertas, salud y gráficas.

🔴 **Un servidor viejo no conoce el código nuevo.** Si algo responde raro después
de tocar el backend, es que `uvicorn` se arrancó sin `--reload`. Pasó dos veces
hoy.

🔴 **Rutas con `:` en Git Bash de Windows.** `git show origin/main:archivo` falla.
Usar `MSYS_NO_PATHCONV=1` adelante.

🔴 **Los heredoc de bash se atragantan con comillas sueltas y con `\s`.** Escribir
documentos largos por consola falla; se escribe el archivo directamente. Y un
`\\s` dentro de un heredoc puede llegar como `\s` y luego degradarse a `s`, que
**borra todas las eses del texto** sin que nada falle.

### De la interfaz y de probarla

🔴 **Se puede manejar Chrome sin instalar nada.** Node 24 ya trae `WebSocket`
global, así que el protocolo DevTools se habla directo: se arranca
`chrome.exe --headless=new --remote-debugging-port=9333`, se lee
`http://127.0.0.1:9333/json/list` y se abre el socket. Con eso se sube un PDF de
verdad por el `<input type=file>` (`DOM.setFileInputFiles`), se navegan las
secciones y se toman capturas. **Es como se verificó todo lo de hoy.**

🔴 **`const` a nivel de script NO queda en `window`.** `Runtime.evaluate` sí lo ve,
porque corre en el ámbito global; pero `iframe.contentWindow.MODULOS` da
`undefined`. Dentro de un iframe hay que usar `w.eval("MODULOS")`.

🔴 **Chrome headless en Windows tiene un ancho mínimo de ventana (~490px).** Una
captura pedida a 390px es una página de 490px recortada y **miente**. Para
verificar responsivo hay que cargar la página en un iframe del ancho buscado y
comparar `scrollWidth` con `clientWidth`.

⚠️ **Enmascarar un elemento desvanece también su texto.** La retícula del dictamen
borraba las letras hasta que se movió a un pseudo-elemento `::before`.

⚠️ **`button:hover:not(:disabled)` tiene más especificidad que `button.primario`**
y le robaba el color, dejando texto claro sobre ámbar (1,8:1, ilegible).

🔴 **Al generar JavaScript desde Python, cuidado con los saltos de línea
escapados.** El método que funciona: escribir el fragmento en un archivo aparte y
que el script lo lea.

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
  2022 son una extensión didáctica coherente, y conservan el balance descuadrado
  a propósito.
- **`andina_con_benchmark.json`** — el trienio con referencias sectoriales.
  🔴 **Esas cifras son ILUSTRATIVAS, no son datos reales del sector.**

⚠️ **Los tres salen en semáforo rojo, y está bien.** Los datos del taller traen el
balance descuadrado (550 en 2023, 390 en 2024) y Pálpito lo dice. No pasan por el
importador, así que ningún cambio del lector puede afectarlos.

---

## Empresas grandes: qué se probó de verdad

**Ecopetrol 2024** (146 páginas): ❌ **no sirve ese PDF.** Las páginas 11-17 —los
estados— son **imágenes escaneadas**. La app lo detecta y avisa dos veces.

**Nutresa 2025** (75 páginas): ✅ **funcionaba** (páginas 10-12, 17 cuentas).
⚠️ **El PDF ya no está en el disco**, así que no se pudo volver a comprobar tras
los cambios de hoy. Lo que se dice de Nutresa en `CRUCES-VISTOS.md §4` es
inferencia, no medición.

**Grupo Argos 2025** (223 páginas, consolidado): ✅ **funciona.** Rango 16-19
detectado solo, 18 cuentas, dos periodos, las cifras cuadran con el informe. La
capa de seguridad sigue trabajando: el puntaje de salud sale marcado
`confiable: false`, porque el catálogo de 23 cuentas no cubre un holding.

**La limitación de diseño que queda:** el catálogo tiene **23 cuentas, pensadas
para una pyme**. Un holding tiene crédito mercantil, intangibles e inversiones en
asociadas que no caben. Por eso la validación reporta que el activo total no
cuadra con activo corriente + PPE. **No invalida el análisis** —liquidez,
márgenes, rotación y rentabilidad no dependen de esas cuentas— pero conviene
decirlo antes de que lo pregunten.

---

## 🔴 Pendientes que son de Oscar, no míos

- ~~**¿Se sube a GitHub?**~~ ✅ **Resuelto el 10-sep-2026.** Oscar lo pidió y se
  subió. De aquí en adelante la pregunta es otra: **si sigue queriendo push cada
  vez, o vuelve a commit local.** Sigue sin subirse solo: preguntar antes.
- **¿Cuándo es la exposición?** El profesor dijo el 2 de septiembre que quedaban
  tres clases y que la última era la nota. **Ya tiene fecha real.**
- **¿Qué exige la rúbrica?** Sin respuesta desde el 29 de agosto.
- **¿Se le entrega el repositorio al profesor, y cómo?** Sin definir.
- **¿Desplegar en `finanzas.torbex.com.co`?** Todo listo; él decidió dejarlo en
  local. No desplegar sin que lo pida.
- **¿Cargar un estado financiero de un negocio suyo?** De Serviteca o del
  restaurante. Sigue sin hacerse, y es la prueba que más le serviría a él: son
  pymes, así que el catálogo de 23 cuentas les queda bien.
- **¿Arreglar el responsivo a 400px?** Cuatro secciones se desbordan. Para
  proyector no molesta.
- **¿Se borran los dos casos sueltos de `casos/`?** Ver arriba. Uno duplica un
  caso del taller.
- **¿Qué empresa se lleva a la exposición?** Almacenes Éxito ya entra limpio y es
  del tipo correcto (compra, guarda y vende). Grupo Bolívar y Grupo Argos salen
  marcados como no confiables, con razón: son un banco y un holding.

---

## Estructura

```
palpito/
├── backend/motor/     modelos · validacion · indicadores · diagnostico
│                      · salud · importacion · narrativa · proyectos
│                      · benchmark · secciones
├── backend/tests/     393 pruebas en 13 archivos
├── backend/api.py     FastAPI: 20 rutas (guardar, borrar y fundir son nuevas)
├── frontend/          index.html, sin frameworks, 7 módulos
├── casos/             3 casos (ver arriba cuál no se toca)
├── docs/DESPLIEGUE.md guía para Dokploy
├── FORMULAS.md        §9 proyectos · §10 EVA · §11 benchmark
│                      §8 los 6 errores del material del curso
├── PRODUCT.md         qué es y para quién
├── DESIGN.md          el sistema visual, escrito desde lo construido
├── CRUCES-VISTOS.md   10 cruces · §8 tiene 2 fuentes · §9 y §10, una
└── .env               🔴 la clave (NO se sube a git)
```

## Para levantar la aplicación

```bash
cd palpito/backend
uvicorn api:app --reload      # → http://localhost:8000
python -m pytest -q           # deben pasar 393
```

⚠️ Los servidores que levanta el asistente **mueren al cerrarse su sesión**. El
día de la exposición hay que levantarlo desde una terminal propia.
