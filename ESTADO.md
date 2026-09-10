# Estado — 10 de septiembre de 2026

## Dónde vamos

**Pálpito** es una aplicación de diagnóstico financiero para *Análisis y Gerencia
Financiera* (Universidad El Bosque). Funciona, y hoy se probó por primera vez
contra un **holding de verdad**: Grupo Argos consolidado 2025.

Verificado hoy, no de memoria:

- **`300 passed`** en 1,95 s — la suite completa
- **Commit `e93d38b` hecho, LOCAL.** 🔴 **Sin subir a GitHub.** Oscar eligió
  commit local sin push. El trabajo sigue existiendo en un solo disco duro.
- Árbol limpio salvo `CRUCES-VISTOS.md` y este `ESTADO.md`, de este cierre
- <https://github.com/restrepogalvezoscarjulian-lgtm/palpito> (MIT)

**La prueba con Argos destapó tres errores del motor.** Están sin arreglar y son
lo primero que sigue. No son del PDF: el PDF está bien.

---

## Lo primero al retomar

**Arreglar los tres errores que destapó Grupo Argos, en este orden.** Oscar ya
decidió el cómo de los dos primeros (ver *Lo que se decidió*).

### Cómo reproducirlos en un minuto

```bash
cd palpito/backend
python -c "
from motor import importacion, secciones
ruta = r'C:\Users\Lenovo\Downloads\0054345457_0066_000058_0000_000000_000000_C-C_2025-12-31.pdf'
datos = open(ruta,'rb').read()
print(secciones.detectar_en_pdf(datos)['paginas'])      # da 19-20, deberia dar 16-19
d = importacion.importar('argos.pdf', datos, paginas='16-19').como_dict()
for f in d['filas']:
    if f['cuenta']: print(f['cuenta'], f['valores'])
"
```

El PDF vive en `C:\Users\Lenovo\Downloads\` (nombre largo que empieza por
`0054345457_`). **No está en el repositorio** y no debería entrar: son 3,75 MB de
un documento público que se puede volver a bajar.

### 1. 🔴 El detector de secciones pierde el activo entero

`motor/secciones.py`, función `analizar_paginas`. Elige **19-20**; lo correcto es
**16-19**. El balance de Argos ocupa tres páginas (16 activos, 17 pasivos, 18
patrimonio) y el detector se queda solo con **la mejor página de cada clase**, así
que descarta la 16 y la 17.

Con el rango automático reconoce **7 cuentas**; con el correcto, **15**.

**Decidido:** que agrupe páginas contiguas que puntúan en la misma clase, en vez
de hacerlas competir entre ellas. Sigue siendo determinista y auditable.

⚠️ **Antes de tocar nada, entienda por qué con Nutresa SÍ acertó** (páginas 10-12,
también repartidas). Está anotado como pregunta abierta en `CRUCES-VISTOS.md §4`.
Arreglar sin entender esa diferencia puede romper el caso que hoy funciona — y hay
pruebas que lo fijan (`test_empresa_grande.py`).

### 2. 🔴 Una cuenta del balance se coló en el estado de resultados

`motor/importacion.py`, el diccionario de sinónimos. Reconoció
**"Activos por impuestos" (257.927)**, que es un activo, y lo guardó como
`impuestos` del estado de resultados. El gasto de renta real es **589.725**.

**El daño se ve en la cifra:** Pálpito calculó una tasa efectiva de impuestos del
**19,49%**. El informe de Argos declara **44,57%** en su Nota 10.3.

**Lo que hay que arreglar:** el diccionario compara etiquetas sin mirar en qué
estado apareció el renglón. Una etiqueta que empieza por *"activos"* no debería
poder caer nunca en resultados.

### 3. 🔴 Confunde todo el pasivo de largo plazo con deuda financiera

`deuda_financiera_lp` capturó **12.492.908**, que es el *total de pasivos no
corrientes*. La deuda financiera real es **7.503.420** (obligaciones financieras
2.945.325 + bonos 4.558.095). **La sobrestima en 66%.**

Es como sumar al banco lo que le debes a proveedores e impuestos por pagar.

Efecto secundario venenoso: como se llevó el total, **la ecuación contable casi
cuadra** (falla por 491, que son los pasivos de activos mantenidos para la venta).
Cuadra por la razón equivocada.

### 4. Después de arreglar: volver a correr las dos cosas

```bash
python -m pytest -q          # deben seguir pasando 300
```

Y repetir la reproducción de arriba con Argos. **Las dos, no una.**

---

## Lo que se decidió, y por qué

Un chat nuevo no puede deducir esto leyendo el código.

### Decidido hoy, 10 de septiembre

**La utilidad neta es la de operaciones continuadas.** Argos ganó 4.346.462 en
2025, pero **733.427** vienen de operar y el resto de vender Summit Materials y
escindirse de Grupo Sura — plata que no se repite. Pálpito toma la continuada
porque es la que sirve para proyectar, y **anota en los supuestos** que dejó fuera
lo discontinuado. *(Hoy toma 733.427 por accidente, no por diseño: hay que
volverlo intencional y que quede anotado.)*

**El detector agrupa páginas contiguas** en vez de elegir la mejor. Ver arriba.

**El commit se hizo local, sin push.** Oscar lo eligió así. **No subir sin que lo
pida.**

**Se borró `nut2023.pdf`.** No era un PDF: eran 919 bytes de una página de error
HTML de una descarga fallida de Nutresa.

### Decisiones de fondo, que siguen vigentes

**La IA nunca calcula.** Sigue siendo la decisión central. El motor calcula y
decide; el modelo recibe números ya resueltos y los traduce a prosa. Conexión:
OpenRouter, `deepseek/deepseek-v4-flash`, clave en `.env` (fuera de git). Hace
cuatro cosas: redacta el diagnóstico, responde preguntas, redacta el concepto de
viabilidad del proyecto, y propone a qué cuenta corresponde una etiqueta
desconocida. **El modelo puede opinar sobre cómo se llama una fila, jamás sobre
cuánto vale.**

**Detectar las páginas de los estados NO usa el modelo.** Se hizo determinista
(`motor/secciones.py`) porque un estado financiero siempre se anuncia con las
mismas palabras: buscarlas es instantáneo, gratis y **auditable**. Un modelo ahí
cobraría, tardaría y podría inventarse una página. **Esta decisión sigue en pie
aunque el detector se haya equivocado hoy** — el arreglo es mejor lógica, no un
modelo.

**Nada externo se inventa.** El WACC y las referencias sectoriales no se deducen
de los estados. Si no se declaran, se reportan como no disponibles. El benchmark
**hereda** la dirección de mejora de `CRITERIOS` en `salud.py`, y una prueba fija
esa igualdad.

**La inversión de un proyecto viaja aparte de los flujos y positiva.** El motor le
pone el signo. Es el error más común del tema.

**Se reportan los dos paybacks, no uno.** La diferencia entre el simple y el
descontado *es* el hallazgo del taller.

**La TIR se resuelve por bisección.** Para más de dos periodos no hay fórmula
cerrada: es un polinomio.

**La dirección visual es un instrumento de registro de precisión.** La eligió
Oscar entre tres opciones. Todo el sistema está en `DESIGN.md`.

**Dos calibraciones, y no son decorativas.** Oscura para pantalla y Teams; clara
de alto contraste para proyector, porque **un proyector de salón lava los negros**.
Botón al pie de la barra lateral.

**Las tildes importan.** En una exposición, "La operacion no genero caja" se lee
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
negativo — pero él concluyó que era positivo. Queda en `FORMULAS.md §8.6` como la
**sexta** discrepancia con el material del curso. La conclusión no cambia (sigue
siendo viable por TIR); cambia la cifra.

---

## Las trampas

Lo que ya costó horas encontrar.

### De la importación de archivos reales

🔴 **Un PDF que "se lee bien" puede estar entregando basura.** Si el documento trae
índice y los estados van escaneados, se lee el índice y los números de página
entran como saldos. Revisar siempre los avisos antes de confirmar.

🔴 **El conteo de páginas escaneadas va sobre el documento COMPLETO**, aunque solo
se lean unas páginas. Al acotar el rango se rompió esto una vez y **el aviso más
importante desapareció** sin que nada fallara.

🔴 **`importacion.py` va sin tildes a propósito.** Su diccionario de sinónimos se
compara contra etiquetas ya normalizadas (el normalizador quita las tildes). Si se
le ponen tildes a las claves, deja de reconocer las cuentas.

🔴 **`unidad="dias"` y `unidad="anios"` son valores de enumeración**, no texto. El
frontend los compara y los traduce al mostrar. No acentuarlos.

🔴 **La columna "Nota" se descarta por POSICIÓN, no por entenderla.** El armador se
queda con los dos últimos números porque hay dos periodos. Con tres periodos
declarados y columna de nota, volvería a fallar. No está comprobado que falle;
está sin comprobar que no. *(Ver `CRUCES-VISTOS.md §1`.)*

⚠️ **Los estados publicados traen costos y gastos entre paréntesis** (negativos)
porque los están restando. Se voltean al armar, **nunca en silencio**: queda
anotado en `supuestos.ajustes_importacion`.

### Del código

🔴 **Reponer tildes con búsqueda y reemplazo ROMPE el código.** Con `\b` el guion
bajo protege `razon_corriente`, pero **nada protege a los identificadores sin
guion bajo**: `formula=` se volvió `fórmula=`. La forma correcta: recorrer con
`tokenize` y tocar **solo tokens STRING que contengan un espacio**.

🔴 **Las f-strings de Python 3.12 no son tokens STRING.** Su texto viaja en
`FSTRING_MIDDLE`, y ahí vive buena parte de la prosa del motor.

🔴 **No le agregue periodos a `comercial_andina.json`.** Las pruebas verifican por
posición: meter un año al frente corre todos los índices y revientan 29. Los casos
nuevos van en archivos nuevos.

🔴 **`validacion.validar()` recibe un `EstadosFinancieros`, no un dict.** Si le
pasa el dict de `armar_estados` directamente, revienta con
`'dict' object has no attribute 'periodos'`. Hay que envolverlo:
`EstadosFinancieros(est)`.

🔴 **`Tabla.como_dict()`, no `a_dict()`.** Y las `Fila` son dataclasses, no
diccionarios: se lee `f.cuenta`, no `f.get("cuenta")`.

🔴 **Para el análisis completo hay atajo:** `api._analizar(ef)` encadena
validación, indicadores, alertas, salud y gráficas. No hay que llamarlos uno a
uno.

🔴 **Un servidor viejo no conoce el código nuevo.** Si algo responde raro después
de tocar el backend, es que `uvicorn` se arrancó sin `--reload`.

🔴 **Rutas con `:` en Git Bash de Windows.** `git show origin/main:archivo` falla.
Usar `MSYS_NO_PATHCONV=1` adelante.

🔴 **Los heredoc de bash se atragantan con el `@'...'@` de PowerShell.** Al hacer
el commit de hoy, el mensaje quedó con un `@` de sobra en el asunto y hubo que
enmendarlo. En Bash se usa `git commit -F -` con heredoc.

🔴 **Un heredoc de bash también se atraganta con comillas sueltas dentro del
texto.** Escribir este mismo `ESTADO.md` por heredoc falló. Para documentos
largos con comillas y barras invertidas, se escribe el archivo directamente, no
por consola.

### De la interfaz

⚠️ **Enmascarar un elemento desvanece también su texto.** La retícula del dictamen
borraba las letras hasta que se movió a un pseudo-elemento `::before`.

⚠️ **`button:hover:not(:disabled)` tiene más especificidad que `button.primario`**
y le robaba el color, dejando texto claro sobre ámbar (1,8:1, ilegible).

🔴 **Chrome headless en Windows tiene un ancho mínimo de ventana (~490px).** Una
captura pedida a 390px es una página de 490px recortada y **miente**. Para
verificar responsivo hay que cargar la página en un iframe del ancho buscado y
comparar `scrollWidth` con `clientWidth`.

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
  2022 son una extensión didáctica coherente con la historia, y conservan el
  balance descuadrado a propósito.
- **`andina_con_benchmark.json`** — el trienio con referencias sectoriales.
  🔴 **Esas cifras son ILUSTRATIVAS, no son datos reales del sector.**

---

## Empresas grandes: qué se probó de verdad

**Ecopetrol 2024** (146 páginas): ❌ **no sirve ese PDF.** Las páginas 11-17 —los
estados— son **imágenes escaneadas**. La app lo detecta y avisa dos veces.

**Nutresa 2025** (75 páginas): ✅ **funciona.** Las páginas se detectan solas
(10-12), 17 cuentas, dos periodos. Verificado contra el PDF: margen bruto 39,46%,
razón corriente 1,97, días de inventario 75,0.

**Grupo Argos 2025** (223 páginas, consolidado): ⚠️ **el PDF sirve; el motor
falla.** Todas las páginas traen texto, detectó los dos periodos solo. Pero salen
los tres errores de arriba. **La capa de seguridad SÍ funcionó**: semáforo rojo, 6
errores, 2 advertencias, y el puntaje de salud (39,5) marcado `confiable: false`
con la advertencia de que no sirve para decidir. Prefirió avisar antes que
entregar un número bonito y falso — que es exactamente lo que se diseñó.

**La limitación de diseño que queda:** el catálogo tiene **23 cuentas, pensadas
para una pyme**. Un holding tiene crédito mercantil, intangibles e inversiones en
asociadas que no caben. Por eso la validación reporta que el activo total no
cuadra con activo corriente + PPE. **No invalida el análisis** —liquidez,
márgenes, rotación y rentabilidad no dependen de esas cuentas— pero conviene
decirlo antes de que lo pregunten.

---

## 🔴 Pendientes que son de Oscar, no míos

- **¿Se sube el commit a GitHub?** Eligió commit local sin push. El commit protege
  de borrar algo por accidente, **no del disco duro**. Sigue existiendo en una
  sola máquina.
- **¿Cuándo es la exposición?** El profesor dijo el 2 de septiembre que quedaban
  tres clases y que la última era la nota. **Ya tiene fecha real.**
- **¿Qué exige la rúbrica?** Sin respuesta desde el 29 de agosto.
- **¿Se le entrega el repositorio al profesor, y cómo?** Sin definir.
- **¿Desplegar en `finanzas.torbex.com.co`?** Todo listo; él decidió dejarlo en
  local. No desplegar sin que lo pida.
- **¿Cargar un estado financiero de un negocio suyo?** De Serviteca o del
  restaurante. Sigue sin hacerse, y es la prueba que más le serviría a él: son
  pymes, así que el catálogo de 23 cuentas les queda bien.

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
├── CRUCES-VISTOS.md   5 cruces · §4 y §5 son de hoy y están sin prueba
└── .env               🔴 la clave (NO se sube a git)
```

## Para levantar la aplicación

```bash
cd palpito/backend
uvicorn api:app --reload      # → http://localhost:8000
python -m pytest -q           # deben pasar 300
```

⚠️ Los servidores que levanta el asistente **mueren al cerrarse su sesión**. El
día de la exposición hay que levantarlo desde una terminal propia.
