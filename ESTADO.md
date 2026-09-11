# Estado — 11 de septiembre de 2026

## Dónde vamos

**Pálpito** es una aplicación de diagnóstico financiero para *Análisis y Gerencia
Financiera* (Universidad El Bosque). Hoy dejó de ser solo un lector de estados
financieros: **ahora también construye la vara con la que los mide**.

Verificado ahora, no de memoria:

- **`445 passed`** — la suite completa (ayer en la mañana eran 393)
- **Almacenes Éxito entra limpio y completo**: 0 errores de calidad, puntaje
  65,0, y las cinco dimensiones de salud evaluadas. Ayer la rentabilidad salía
  "sin datos".
- **El benchmark sectorial se calcula solo.** Un sector construido: CIIU 4711
  (comercio al por menor con surtido de alimentos), corte 2024, **155 empresas**,
  16 indicadores con mediana y cuartiles. Se escoge de un desplegable en la app.
- 🔴 **4 commits sin subir.** `main...origin/main [ahead 4]`. Lo de estos dos
  días existe en un solo disco duro.
- <https://github.com/restrepogalvezoscarjulian-lgtm/palpito> (MIT)

---

## Lo primero al retomar

### 1. Preguntarle a Oscar si se hace push

Son **4 commits**: `11f74fe`, `cfabb3c`, `e62f9a2`, `7e2defe`, `66428ab`,
`fa0a38c` (los cuatro últimos sin subir). Ha dicho que sí las dos veces que se
le preguntó, **pero sigue preguntándose cada vez**. No es automático.

### 2. La pregunta que quedó abierta y a medio investigar

Oscar preguntó el 11-sep: **¿se puede cargar una empresa escribiendo su nombre,
en vez de subirle un PDF?** Se investigó y **SÍ se puede**. Falta construirlo.

Lo verificado:

- El directorio `dd55-74ss` ("Sujetos obligados") tiene **161.771 empresas con
  NIT y razón social**. Buscar "D1 S.A.S" devuelve el NIT 900276962.
- Con ese NIT, los estados salen de los mismos datasets que ya usa el benchmark.
- **`herramientas/supersociedades.armar_estados()` ya hace la conversión.** Es
  la misma función; lo que falta es la pantalla y la ruta.
- **29.362 empresas** tienen balance del corte 2024.

🔴 **Dos límites que hay que decirle antes de construirlo** *(ya se le dijeron)*:

- **Las que cotizan en bolsa NO están**: Éxito, Ecopetrol, Argos, Nutresa,
  Bancolombia le reportan a la **Superfinanciera**, no a Supersociedades. Para
  esas sigue el PDF. Esto **complementa** el importador, no lo reemplaza.
- 🔴 **Resgaval SAS NO aparece** en los 161.771 obligados (comprobado). La
  empresa de Oscar no le reporta a Supersociedades, así que para **Serviteca y
  el restaurante** seguiría siendo Excel o digitación a mano — que era justo la
  prueba que más le servía a él.

⚠️ **Y una corrección a cómo lo planteó:** él dijo "que la inteligencia
artificial investigue". **Aquí no hace falta IA y es mejor que no la haya.** Es
una consulta determinista: se pide un NIT y llega la cifra exacta, siempre la
misma, auditable. Meter un modelo reabriría justo el riesgo que el proyecto
lleva meses cerrando.

### 3. Levantar el servidor antes de probar nada en el navegador

Ver el final de este archivo. **Con `--reload` no basta**: ver *Las trampas*.

---

## Lo que se hizo estos dos días

### 10-sep — los estados reales entran limpios

| | Antes | Ahora |
|---|---|---|
| Errores en Éxito 2024 | 10 | **0** |
| `ventas` | 60.481 (un renglón de derivados) | **21.880.509** |
| Días de inventario | 3.614 (diez años) | **62,9** |
| Rentabilidad en el puntaje | 🔴 **sin datos** | **70,7** |

Cuatro causas de la primera tanda, todas nuestras: faltaban `pasivo_total` y
`pasivo_no_corriente` en el catálogo del importador; renglones del flujo de
efectivo se disfrazaban de resultados; el diccionario elegía por frase más larga
en vez de por posición; y un error que no era un error.

Y una quinta que salió del ensayo de la exposición: **la guarda contra el flujo
de efectivo se comía la utilidad operacional**. *(`CRUCES-VISTOS.md §11`.)*

### 11-sep — el benchmark se construye solo

**La idea:** no hacía falta un motor nuevo. Pálpito ya sabe convertir un balance
en 28 indicadores; dándole las 29.362 sociedades que le reportan a la
Superintendencia, devuelve el benchmark del país. **La misma máquina que analiza
una empresa construye la vara con la que se la mide.**

```
CIIU -> NITs -> balance y resultados -> las 23 cuentas -> indicadores
     -> mediana y cuartiles -> referencias/ciiu-XXXX.json
```

**Almacenes Éxito contra las 155 empresas de su CIIU**, y la historia es DuPont
puro — sirve tal cual para la sustentación:

| | Éxito | Sector |
|---|---|---|
| Margen bruto | **25,6 %** | 16,2 % |
| Días de proveedores | **95,2** | 37,1 |
| Ciclo de caja | **−24,8** | +9,2 |
| Rotación de activos | **1,26** | 3,80 |
| **ROE** | **9,4 %** | **12,2 %** |

Gana en las dos palancas que se negocian —margen y plazo de proveedores— y **aun
así su ROE es menor**, porque rota sus activos un tercio de lo que rota el
sector. Es dueño de sus hipermercados mientras D1 y Ara arriendan locales
pequeños: el ladrillo infla el activo y hunde la rotación.

⚠️ **Decirlo antes de que lo pregunten:** las cifras de Éxito son del
**consolidado** (incluye Uruguay y Argentina); las del sector, de operaciones en
Colombia.

---

## Lo que se decidió, y por qué

Un chat nuevo no puede deducir esto leyendo el código.

### Decidido estos dos días

**El benchmark se mapea por nombre EXACTO, con diccionario propio**, y no por
subcadena como el importador de PDF. Un PDF trae etiquetas libres y hay que
adivinar; la taxonomía de Supersociedades trae **73 conceptos fijos en el balance
y 28 en resultados**. Adivinar ahí no solo sobra: hace daño.
*(`CRUCES-VISTOS.md §11`.)*

**Mediana y cuartiles, nunca promedio.** Siempre hay una empresa que vendió un
activo. Y con cuartiles se puede decir *"está en el cuartil superior del
sector"*, que es como habla un analista.

**La aplicación NUNCA consulta internet.** Lee `referencias/` del disco.
Reconstruir un sector es un acto deliberado que se corre aparte. El día de la
exposición no puede depender del wifi del salón.

**Las referencias guardan su procedencia** —año, cuántas empresas, fuente y
fecha de descarga— y se muestra en pantalla. Una referencia que no se puede
sustentar ante quien pregunte no sirve para comparar nada.

**La deuda financiera se deja fuera del benchmark a propósito.** Bajo NIIF va
mezclada con derivados en "Otros pasivos financieros". Sumarla sobrestimaría el
endeudamiento, que es el error que costó **66 %** en Grupo Argos. Los
indicadores que dependen de ella dicen "no disponible", igual que para Éxito.

**El encadenamiento del estado de resultados se degrada a advertencia** cuando
el catálogo no explica el activo. En Éxito, "operacional − financieros" da
196.444 y él declara 292.908: los 96.464 de diferencia son ingresos financieros
y método de participación que las 23 cuentas no recogen. **En una pyme sigue
siendo ERROR**, porque ahí un descuadre es un descuadre.

### Decisiones de fondo, que siguen vigentes

**La IA nunca calcula.** Sigue siendo la decisión central. El motor calcula y
decide; el modelo recibe números ya resueltos y los traduce a prosa. OpenRouter,
`deepseek/deepseek-v4-flash`, clave en `.env` (fuera de git). Hace cuatro cosas:
redacta el diagnóstico, responde preguntas, redacta el concepto de viabilidad, y
propone a qué cuenta corresponde una etiqueta desconocida. **El modelo puede
opinar sobre cómo se llama una fila, jamás sobre cuánto vale.**

⚠️ **Y darle datos mal etiquetados la rompe igual que darle datos sin calcular.**
`narrativa.py` usa `diagnostico.renglon_de_caja` a propósito: si al modelo le
llega "Consumido" sobre una partida que liberó caja, redacta lo contrario de lo
que pasó.

**Detectar las páginas de los estados NO usa el modelo.** Determinista, porque un
estado financiero siempre se anuncia con las mismas palabras: instantáneo,
gratis y **auditable**.

**Nada externo se inventa.** El WACC y las referencias sectoriales no se deducen
de los estados. Si no se declaran, se reportan como no disponibles.

**La inversión de un proyecto viaja aparte de los flujos y positiva.** El motor
le pone el signo. Es el error más común del tema.

**Se reportan los dos paybacks**, y **la TIR se resuelve por bisección**.

**La dirección visual es un instrumento de registro de precisión.** La eligió
Oscar entre tres opciones. Todo el sistema está en `DESIGN.md`. **Dos
calibraciones**: oscura para pantalla, clara de alto contraste para proyector,
porque un proyector de salón lava los negros.

**Las tildes importan.** En una exposición, "La operacion no genero caja" se lee
como descuido — y esa frase **estuvo en el código hasta el 10-sep**. Matices:
`importacion.py` va sin tildes **solo en las claves del diccionario**; la prosa
que ve el usuario las lleva. **Los comentarios del código se dejan sin tildes a
propósito** (decisión de Oscar el 10-sep: solo se corrige lo que se ve en
pantalla).

**Los números van a la colombiana**: punto de miles, coma decimal. `_num` y
`_pct` en `proyectos.py`.

---

## Las trampas

Lo que ya costó horas encontrar.

### De las fuentes de datos

🔴 **EL PORTAL DE DATOS ABIERTOS ENTREGA EL DATO YA CORRUPTO.** Las vocales
acentuadas llegan como `EF BF BD` —U+FFFD bien codificado— así que
`"Ganancia (pérdida)..."` no empata con nada. No es un problema de
decodificación de este lado. Se comparan los dos lados por su **esqueleto
ASCII**. Sin esto, el benchmark salía sin margen operacional, sin margen neto,
sin ROA y sin ROE, **y nada fallaba: los indicadores simplemente no aparecían**.
*(`CRUCES-VISTOS.md §12`.)*

🔴 **El archivo de las "10.000 empresas más grandes" NO sirve para ratios.** Trae
las cifras en billones redondeadas a dos decimales: toda empresa que gane menos
de 5.000 millones tiene ganancia **0,00**. Daba mediana de margen neto, ROA y
ROE **de 0,00 %**. Sirve para ordenar por tamaño y nada más.
*(`CRUCES-VISTOS.md §13`.)*

🔴 **La API del portal necesita HTTPS.** Con `http://` devuelve vacío sin error.

🔴 **Los que cotizan en bolsa no están en Supersociedades.** Éxito, Ecopetrol,
Argos, Nutresa, Bancolombia → Superfinanciera. Se ve en el campo `supervisor`.

⚠️ **Los ratios no dependen de la unidad.** Da igual que el archivo venga en
pesos o en miles: al dividir se cancela. Hay una prueba que lo fija.

### De la importación de archivos reales

🔴 **Un PDF que "se lee bien" puede estar entregando basura.** Si trae índice y
los estados van escaneados, entran números de página como saldos.

🔴 **El conteo de páginas escaneadas va sobre el documento COMPLETO.**

🔴 **Una nota del fondo del documento puede puntuar más que el estado de verdad.**
*(`CRUCES-VISTOS.md §4`.)*

🔴 **Leer una página de más puede cambiar una cifra sin avisar.** El rango de
páginas **es un dato de entrada**, no un detalle de rendimiento.

🔴 **El lector de PDF pega el total con el encabezado siguiente.** Produce
`"total pasivos corrientes pasivos no corrientes"`. El corte mira **de qué es el
total**, con un `.*?` perezoso.

🔴 **El archivo trae los TRES estados y los del flujo se disfrazan.** Los verbos
delatan: *compras de*, *adiciones*, *adquisición*, *antes de cambios en*.

🔴 **Pero la guarda del flujo puede comerse un resultado legítimo.** Bajo NIIF la
utilidad operacional se llama *"Ganancia por actividades de operación"*. Manda
**cómo empieza** la etiqueta. *(`CRUCES-VISTOS.md §11`.)*

🔴 **Los plurales van explícitos en el diccionario.**

🔴 **`importacion.py` va sin tildes SOLO en las claves.** Los avisos que lee el
usuario **sí las llevan**. Dos pruebas fijan las dos mitades.

🔴 **`unidad="dias"` y `unidad="anios"` son valores de enumeración**, no texto.

🔴 **La columna "Nota" se descarta por POSICIÓN.** Con tres periodos declarados y
columna de nota, volvería a fallar. *(`CRUCES-VISTOS.md §1`.)*

⚠️ **Los estados publicados traen costos y gastos entre paréntesis.** Se voltean
al armar, **nunca en silencio**. *(`CRUCES-VISTOS.md §7`.)*

### Del código

🔴 **`totales?` no significa "total" u "opcionalmente totales".** El `?` aplica
solo a la letra anterior. Lo correcto es `total(?:es)?`.

🔴 **Reponer tildes con búsqueda y reemplazo ROMPE el código.** `formula=` se
volvió `fórmula=`. Recorrer con `tokenize` y tocar **solo tokens STRING con un
espacio**. Y **las f-strings de Python 3.12 no son tokens STRING**: su texto
viaja en `FSTRING_MIDDLE`.

🔴 **No le agregue periodos a `comercial_andina.json`.** Las pruebas verifican por
posición: meter un año al frente revienta 29.

🔴 **`validacion.validar()` recibe un `EstadosFinancieros`, no un dict.**

🔴 **`Tabla.como_dict()`, no `a_dict()`.** Las `Fila` son dataclasses.

🔴 **Para el análisis completo hay atajo:** `api._analizar(ef)`.

🔴 **`importar(nombre, contenido)`** — el nombre va PRIMERO.

🔴 **`Proyecto` usa `inversion`, no `inversion_inicial`**, y la función es
`evaluar_proyecto`.

🔴 **Un servidor viejo no conoce el código nuevo.** `--reload` **no siempre
basta**: el 10-sep hubo que matar y relevantar uvicorn para que el importador
nuevo se viera. Si algo responde raro después de tocar el backend, **relevántelo
de cero**.

🔴 **Rutas con `:` en Git Bash de Windows.** Usar `MSYS_NO_PATHCONV=1` adelante.

🔴 **Los heredoc de bash se atragantan con comillas sueltas y con `\s`.**

⚠️ **La consola de Windows es cp1252 y revienta al imprimir texto con tildes o
U+FFFD.** Usar `PYTHONIOENCODING=utf-8` adelante.

### De la interfaz y de probarla

🔴 **EL NAVEGADOR REUSA EL `index.html` DE LA CARGA ANTERIOR.** El 10-sep la
prueba corrió **dos veces dando el resultado viejo idéntico**, sin que nada
fallara, mientras el arreglo ya estaba en disco. En el guion de DevTools hay que
mandar `Network.setCacheDisabled {cacheDisabled:true}` **antes de navegar**.

🔴 **Se puede manejar Chrome sin instalar nada.** Node 24 trae `WebSocket`
global: se arranca `chrome.exe --headless=new --remote-debugging-port=9333`, se
lee `http://127.0.0.1:9333/json/list` y se abre el socket. Con
`DOM.setFileInputFiles` se sube un PDF de verdad. **Es como se verificó todo.**

⚠️ **`DOM.setFileInputFiles` ya dispara el evento `change`.** Dispararlo a mano
además falla, porque el importador ya repintó y el input desapareció.

🔴 **`const` y `let` a nivel de script NO quedan en `window`.** `datosCaso`
existe para `Runtime.evaluate` pero `window.datosCaso` es `undefined`.

🔴 **Chrome headless en Windows tiene ancho mínimo (~490px).** Una captura a
390px **miente**.

⚠️ **`confirm()` bloquea al navegador headless.** Hay que atender
`Page.javascriptDialogOpening`.

⚠️ **Enmascarar un elemento desvanece también su texto.**

⚠️ **`button:hover:not(:disabled)` tiene más especificidad que `button.primario`.**

### Del despliegue

🔴 **El Dockerfile NUNCA se ha construido.** No hay Docker en el PC.

🔴 **En Dokploy: usar tipo "Application", NO "Compose".**

---

## Los casos, y cuál no se toca

- **`comercial_andina.json`** — el del taller, dos periodos. 🔴 **NO MODIFICAR.**
  Es la evidencia de auditoría del proyecto.
- **`andina_trienio.json`** — el mismo caso con 2022 por delante.
- **`andina_con_benchmark.json`** — el trienio con referencias.
  🔴 **Esas cifras son ILUSTRATIVAS, no son datos reales del sector.**

⚠️ **Los tres salen en semáforo rojo, y está bien.** Los datos del taller traen
el balance descuadrado a propósito. No pasan por el importador.

✅ **Los dos casos sueltos se borraron el 10-sep.** Uno era un Frankenstein: el
nombre de Comercial Andina con las cifras de Éxito adentro, producto del defecto
de la casilla "Añadir estos años". Ya está arreglado.

---

## Empresas grandes: qué se probó de verdad

**Almacenes Éxito 2024 + 2025**: ✅ **el caso de referencia.** 20 cuentas, tres
periodos (2023-2024-2025), 0 errores, puntaje 65,0. Los dos PDF están en
`C:\Users\Lenovo\Downloads\exito 2024.pdf` y `exito 2025.pdf`.

**Grupo Argos 2025** (223 páginas): ✅ funciona. Rango 16-19 detectado solo.

**Ecopetrol 2024**: ❌ **no sirve ese PDF.** Las páginas de los estados son
imágenes escaneadas. La app lo detecta y avisa dos veces.

**Nutresa 2025**: ⚠️ funcionaba, pero **el PDF ya no está en el disco**.

**La limitación de diseño:** el catálogo tiene **23 cuentas, pensadas para una
pyme**. Un holding no cabe. No invalida el análisis —liquidez, márgenes,
rotación y rentabilidad no dependen de esas cuentas— pero conviene decirlo antes
de que lo pregunten.

⚠️ **La deuda financiera de Éxito no se importa, a propósito.** En su balance se
llama "Créditos y préstamos" **dos veces con el mismo nombre**, una en el
corriente y otra en el no corriente, y el diccionario no sabe en qué parte del
balance apareció cada renglón. Adivinar sobrestimaría el endeudamiento.

---

## 🔴 Pendientes que son de Oscar, no míos

- **¿Se hace push de los 4 commits?** Preguntar cada vez.
- **¿Cuándo es la exposición?** 🔴 **Sin respuesta desde el 2 de septiembre**, y
  se le ha preguntado cuatro veces. **Es el dato que decide qué se construye y
  qué no.**
- **¿Qué exige la rúbrica?** Sin respuesta desde el 29 de agosto.
- **¿Se le entrega el repositorio al profesor, y cómo?** Sin definir.
- **¿Se construye la carga de empresas por nombre/NIT?** Investigado y viable
  (ver *Lo primero al retomar*). Falta su visto bueno y saber la fecha.
- **¿Se construyen más sectores de benchmark?** Hay uno. El comando es:
  `python -m herramientas.construir_benchmark <CIIU> <año> "<nombre>"`
- **¿Desplegar en `finanzas.torbex.com.co`?** Todo listo; él decidió local.
- **¿Arreglar el responsivo a 400px?** Cuatro secciones se desbordan.
- **¿Qué empresa se lleva a la exposición?** Almacenes Éxito ya entra limpio,
  tiene benchmark sectorial y una historia DuPont redonda.
- ⚠️ **Cargar un estado de un negocio suyo** sigue sin hacerse, y ahora se sabe
  que **no se puede automatizar**: Resgaval no le reporta a Supersociedades.
  Tendría que ser a mano.

---

## Estructura

```
palpito/
├── backend/motor/       modelos · validacion · indicadores · diagnostico
│                        · salud · importacion · narrativa · proyectos
│                        · benchmark · secciones
├── backend/herramientas/ supersociedades.py · construir_benchmark.py
│                        (construyen las referencias; NO los usa la app)
├── backend/tests/       445 pruebas en 14 archivos
├── backend/api.py       FastAPI: 23 rutas
├── frontend/            index.html, sin frameworks, 7 secciones
├── casos/               3 casos del taller (ver cuál no se toca)
├── referencias/         ciiu-471100.json — el benchmark del sector
├── docs/DESPLIEGUE.md   guía para Dokploy
├── FORMULAS.md          §8 los 6 errores del material del curso
├── PRODUCT.md · DESIGN.md
├── CRUCES-VISTOS.md     13 cruces
└── .env                 🔴 la clave (NO se sube a git)
```

## Para levantar la aplicación

```bash
cd palpito/backend
uvicorn api:app --reload      # → http://localhost:8000
python -m pytest -q           # deben pasar 445
```

Para reconstruir un sector del benchmark (tarda unos minutos, usa internet):

```bash
cd palpito/backend
PYTHONIOENCODING=utf-8 python -m herramientas.construir_benchmark 4711.00 2024 "Comercio al por menor"
```

⚠️ Los servidores que levanta el asistente **mueren al cerrarse su sesión**. El
día de la exposición hay que levantarlo desde una terminal propia.
