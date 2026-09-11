# Cruces vistos

Coincidencias entre fuentes que no se conocen entre sí. Se anotan en el momento
en que aparecen, con su origen, porque a la semana ya no se puede verificar de
dónde salieron.

**Cómo se cuentan las fuentes:** dos cosas del mismo autor son **una** fuente.
Coinciden porque piensa igual, no porque la idea se sostenga sola.

---

## 1. En un estado financiero publicado hay números que no son cifras contables

**Fuentes independientes: 3** (tres emisoras distintas, tres documentos distintos)

- **Ecopetrol**, informe consolidado 2024: la tabla de contenido tiene la misma
  forma que un estado financiero —concepto a la izquierda, número a la derecha—
  pero ese número es **una página**. Produjo `Propiedades, planta y equipo = 63`.
- **Nutresa**, informe consolidado 2025: la primera columna de cada renglón es
  **el número de nota**: `Inventarios | 11 | 2.558.764 | 2.447.873`. Con dos
  periodos se guardaba `[11, 2.558.764]`.
- **Grupo Argos**, consolidado 2025 *(10-sep-2026)*: la misma columna de nota,
  otra vez: `Ventas | 33 | 10.689.943 | 12.277.491` llegó al lector como
  `[33, 10.689.943, 12.277.491]`. **Esta vez el armador la descartó bien** y
  guardó los dos últimos valores. La defensa aguantó en un tercer documento
  que no conocía a los otros dos.

**La regla que sale:** en un documento financiero, un número pequeño y aislado
junto a un concepto **casi nunca es un saldo**. Es una página, una nota o un
año. La cifra contable es la que está en la cola del renglón y tiene separador
de miles.

**Estado: comprobado.** Los tres casos se reprodujeron con el archivo real; los
dos primeros tienen pruebas que los fijan (`test_empresa_grande.py`). El de
Argos **todavía no tiene prueba**: se verificó a mano el 10-sep-2026.

⚠️ **Ojo con el matiz:** el armador acierta **por posición** —se queda con los
dos últimos números porque hay dos periodos—, no porque entienda que ese 33 es
una nota. Con tres periodos declarados y una columna de nota, volvería a fallar.
No está comprobado que falle; está sin comprobar que no.

---

## 2. Un semáforo emitido en dos sitios distintos termina contradiciéndose

**Fuentes independientes: 2** (una decisión de diseño propia y una
implementación ajena que no la tomó)

- **Pálpito** decidió por diseño que un solo motor emitiera todos los veredictos,
  y que el benchmark heredara la dirección de mejora de `CRITERIOS` en
  `salud.py` en vez de redefinirla.
- **FinDiag**, la herramienta de unas compañeras del curso, calcula el semáforo
  en cada módulo: en la misma sesión el **ROE sale "Favorable" en Indicadores
  (39,9%) y "Crítico" en Benchmark (29,6%)**, y la *Razón corriente* muestra un
  valor y al lado "Dato no disponible".

**La regla que sale:** cuando el mismo juicio se calcula en dos lugares, la
contradicción no es un riesgo teórico, aparece sola. El criterio se define una
vez y los demás módulos lo leen.

**Estado: comprobado del lado ajeno** (visto en tres capturas de FinDiag),
**y fijado del lado propio** con una prueba que compara `MEJORA` contra
`CRITERIOS`. Lo que NO se verificó es *por qué* FinDiag se contradice: se está
infiriendo de las capturas, no de su código.

---

## 3. Lo que el profesor pide, lo pide dos veces y de dos maneras

**Fuentes independientes: 1** (el mismo profesor, dos momentos de la misma clase)

⚠️ **Cuenta como UNA fuente**, no dos: es la misma persona.

En la sesión 6 pidió tooltips explicando indicadores, primero mostrando su
propia herramienta de mercado de capitales y después dictándole a una alumna la
palabra exacta. Que lo repita es señal de que **pesa en la calificación**, no de
que la idea esté doblemente respaldada.

**Estado: observación, no regla.**

---

## 4. Un estado financiero no cabe necesariamente en una página

**Fuentes independientes: 1** (Grupo Argos, consolidado 2025)

⚠️ **Una sola fuente: es una observación, no una regla.**

El **estado de situación financiera de Grupo Argos ocupa tres páginas** —activos
en la 16, pasivos en la 17, patrimonio en la 18—, cada una repitiendo el mismo
título. El detector de secciones de Pálpito puntúa página por página y se queda
con **la mejor de cada clase**, así que eligió la 18 (la del patrimonio, que
trae "total pasivos" y "total patrimonio") y **descartó las dos primeras**.
Resultado: se perdió el activo entero.

**Lo que sugiere:** puntuar páginas sueltas y quedarse con la mejor asume que
cada estado vive en una hoja. Habría que agrupar páginas contiguas que puntúan
en la misma clase, en vez de competir entre ellas.

**La pregunta abierta quedó respondida el 10-sep-2026, y la respuesta corrige
lo de arriba.** El detector no eligió la página 18. Eligió la **82**, que es
una nota del fondo del documento. Los puntajes medidos, no recordados:

| Página | Clase | Puntaje | Qué es |
|---|---|---|---|
| 16 | balance | 6 | activos ✅ |
| 17 | balance | 6 | pasivos ✅ |
| 18 | balance | 7 | patrimonio ✅ |
| **82** | **balance** | **8** | **una nota** ❌ |
| 108 | balance | 8 | otra nota ❌ |

Así que eran **dos fallas encadenadas**: repartir el balance en tres hojas le
baja el puntaje a cada una, y una nota concentrada les gana a todas. Luego, como
la 82 y la 19 quedaban a 63 páginas, se disparó la regla de dispersión y el
balance se perdió entero.

**Por qué Nutresa sí funcionó:** su balance alcanzaba puntaje suficiente para
ganarle a sus propias notas, y la "página de cola" que el detector sumaba tapó
la tercera hoja **de casualidad**. No acertó por buena lógica; acertó porque el
documento era más benévolo. ⚠️ Esta mitad es **inferencia, no medición**: el PDF
de Nutresa ya no está en el disco. La mitad de Argos sí está medida.

**La regla que salió:** agrupar páginas contiguas de la misma clase en bloques
que suman puntaje, y elegir **la pareja balance+resultados que va junta**, en
vez del mejor de cada clase por separado. Los estados van seguidos; una nota que
habla de activos no tiene un estado de resultados al lado, el balance sí.

**Estado: arreglado y fijado.** `motor/secciones.py` ahora agrupa. Argos da
16-19 con el balance de tres hojas puntuando 19 contra los 8 de la nota. Cuatro
pruebas en `test_secciones.py` lo fijan.

⚠️ **Y se quitó la página de cola**, que resultó ser peligrosa: incluir la 20 de
Argos subía la utilidad neta de 733.427 a 4.346.462. Ver §6.

---

## 5. Dos cuentas que se llaman casi igual y viven en estados distintos

**Fuentes independientes: 1** (Grupo Argos, consolidado 2025)

⚠️ **Una sola fuente: observación, no regla.**

En el balance de Argos hay **"Activos por impuestos" (257.927)**, que es un
activo. En el estado de resultados hay **"Impuesto sobre las ganancias"
(589.725)**, que es el gasto de renta. El diccionario de `importacion.py`
reconoció el primero y lo guardó como el impuesto del estado de resultados.

**El daño se ve en la cifra:** la tasa efectiva de impuestos salió **19,49%**
cuando el propio informe declara **44,57%** en la Nota 10.3. Más del doble de
diferencia, sin que nada fallara.

**Lo que sugiere:** el diccionario compara etiquetas sin mirar **en qué estado
apareció el renglón**. Una etiqueta que empieza por "activos" no debería poder
caer nunca en el estado de resultados.

**Estado: arreglado y fijado el 10-sep-2026.** La regla que se implementó es más
ancha que la sugerencia: una etiqueta que **empieza** por activo/activos/pasivo/
pasivos, o que dice **"por pagar"**, **"por cobrar"** o **"diferido"**, nombra
algo que la empresa tiene o debe hoy, no algo que gastó durante el año, y por eso
no puede llevarse ninguna cuenta del estado de resultados.

Hizo falta la parte de "diferido" porque apareció una tercera trampa que la
observación original no cubría: **"Impuesto diferido" (2.720.397)**, en el pasivo
no corriente, también se colaba como gasto de renta. Nueve pruebas lo fijan, y la
tasa efectiva de Argos ahora da **44,57%**, igual que su Nota 10.3.

---

## 6. Un estado de resultados publicado trae dos utilidades netas, y la grande es la que no sirve

**Fuentes independientes: 1** (Grupo Argos, consolidado 2025)

⚠️ **Una sola fuente: observación, no regla.**

El estado de resultados de Argos declara tres renglones seguidos:

- `UTILIDAD NETA OPERACIONES CONTINUADAS` — **733.427**
- `UTILIDAD NETA OPERACIONES DISCONTINUADAS` — **3.613.035**
- `UTILIDAD NETA` — **4.346.462**

La grande es cinco veces la de operar, y es la que un lector distraído copia. Lo
discontinuado fue vender Summit Materials y escindirse de Grupo Sura: entra una
vez y no vuelve. Proyectar sobre ella es proyectar un milagro.

**Lo que lo hace traicionero es cómo se elegía.** El diccionario prefiere la
coincidencia exacta, así que el renglón pelado `UTILIDAD NETA` le ganaba a
`UTILIDAD NETA OPERACIONES CONTINUADAS`, que es más largo. Hasta el 10-sep la
continuada ganaba **solo porque aparecía primero en la página**. Bastaba con leer
una hoja más —la 20, la del resultado integral, que repite `UTILIDAD NETA` con el
total— para que la cifra cambiara de 733.427 a 4.346.462 **sin que nada avisara**.

**La regla que sale:** cuando un estado ofrece la misma cuenta en versión
"continuada" y en versión "total", la continuada gana siempre, sin importar el
orden ni cuál empate mejor con el diccionario. Y como es una decisión, tiene que
quedar escrita donde el usuario la lea.

**Estado: arreglado y fijado.** Leer Argos con 16-19, 16-20 o 16-21 da ahora la
misma utilidad neta. Seis pruebas lo fijan.

---

## 7. Un campo que se escribe y nadie lee es lo mismo que no escribirlo

**Fuentes independientes: 1** (el propio Pálpito)

⚠️ **Una sola fuente, y es de casa: observación, no regla.**

`armar_estados` anotaba cada ajuste en `supuestos.ajustes_importacion` —el volteo
de signo de los costos, y desde hoy la suma de la deuda—, y el código decía en un
comentario "se voltean, pero **NUNCA en silencio**: cada volteo queda anotado en
los supuestos **y se reporta**".

Al buscar quién leía ese campo el 10-sep-2026, la respuesta fue **nadie**: ni la
interfaz, ni la validación, ni el diagnóstico. Se escribía en el JSON y ahí moría.
El motor llevaba semanas transformando cifras en silencio mientras el código
afirmaba lo contrario.

**Lo que sugiere:** un principio de diseño no está implementado hasta que alguien
consume su salida. Escribirlo en una estructura de datos es la mitad del trabajo,
y es la mitad que se puede confundir con el todo, porque el comentario ya está
escrito y suena a hecho.

**Estado: arreglado.** El análisis lo entrega junto a la validación y el Dictamen
lo pinta bajo *"Lo que Pálpito ajustó al leer el archivo"*. Con Argos salen cinco
ajustes. Dos pruebas en `test_api.py` lo fijan.

Efecto secundario que valió la pena: al volverse visible, ese texto **tuvo que
llevar tildes**. Iba sin ellas porque `importacion.py` va sin tildes a propósito
—su diccionario se compara contra etiquetas normalizadas—, pero esa restricción
aplica **solo a las claves**, no a la prosa. Hay dos pruebas que fijan las dos
mitades: las claves sin tildes, los avisos con ellas.

---

## 8. Una página que HABLA de los estados puntúa como si los TUVIERA

**Fuentes independientes: 2** (dos emisoras distintas, dos partes distintas del
documento)

- **Ecopetrol**, consolidado 2024: la **tabla de contenido** nombra los tres
  estados en tres renglones seguidos. Disparaba todos los marcadores de título y
  se llevaba el puntaje más alto del documento. *(Ya estaba cubierto con la
  regla de los puntos suspensivos.)*
- **Grupo Bolívar**, consolidado 2024 *(10-sep-2026)*: las **notas contables**
  mencionan los estados por su nombre cada dos párrafos —"la ganancia se
  reconoce en el estado de resultados", "se presenta en el estado de situación
  financiera"—. Tres páginas seguidas de prosa sumaban **12 puntos** contra los
  **4** del balance verdadero de la página 14.

**Lo que las une:** las dos son páginas que **hablan** de los estados sin
contener ninguno. El índice se reconocía por su forma; las notas no tienen forma
propia, se ven como prosa cualquiera.

**La regla que sale:** lo que distingue a la página que TIENE el estado no es el
título —que cualquiera puede mencionar— sino los **renglones de saldo**: "total
activos 289.387.918". Solo las páginas con renglones forman bloque. **Sumar
prosa no hace un estado financiero.**

⚠️ **Y hay una lección propia, más incómoda:** esa suma de páginas contiguas la
introduje yo esa misma mañana para arreglar el caso de Grupo Argos. El arreglo de
un documento rompió otro. Un cambio en el detector no se puede probar contra un
solo informe.

**Estado: comprobado en los dos.** Argos sigue dando 16-19 y Bolívar 2024 pasó de
65-67 (notas) a 14-15 (los estados). Tres pruebas lo fijan.

---

## 9. Los tres estados viven en el mismo archivo, y sus renglones se disfrazan

**Fuentes independientes: 1** (Almacenes Éxito, consolidado 2024)

⚠️ **Una sola fuente: observación, no regla.**

Un archivo de estados financieros trae el balance, el estado de resultados **y el
flujo de efectivo**, uno detrás de otro. Los renglones del tercero se parecen a
los del segundo lo bastante como para colarse:

| Renglón del FLUJO DE EFECTIVO | Se coló como | Daño |
|---|---|---|
| "Resultado operacional **antes de cambios en el capital de trabajo**" | utilidad operacional | cifra ajena |
| "**Compras de** propiedades, planta y equipo" (284.669) | compras de mercancía | **días de inventario: 3.614 en vez de 63** |

El segundo es el venenoso. El motor prefiere `compras` sobre `costo_ventas`
cuando existe, así que una línea de inversión secuestró la rotación de
inventario y dio **diez años de mercancía en bodega** para un supermercado.

**Lo que sugiere:** un renglón que cuenta lo que se COMPRÓ o se VENDIÓ durante el
año es un movimiento de caja, no un saldo ni un resultado. Los verbos delatan:
*compras de*, *adiciones*, *adquisición*, *venta de*, *antes de cambios en*.

**Estado: comprobado a mano el 10-sep-2026** con el informe real. Los días de
inventario de Éxito pasaron de 3.614 a 62,9.

---

## 10. Un error que no es un error entrena a no leer los errores

**Fuentes independientes: 1** (el propio Pálpito)

⚠️ **Una sola fuente, y es de casa.**

La validación marcaba como **error** que "activo corriente + PPE" no sumara el
activo total. En Almacenes Éxito faltaban así **7,8 billones** —crédito
mercantil, intangibles, inversiones en asociadas, derechos de uso—, ninguno de
los cuales cabe en el catálogo de 23 cuentas.

O sea que un balance **perfectamente cuadrado** salía con semáforo rojo por una
diferencia que es **normal en toda empresa mediana o grande**.

**Lo que sugiere:** la asimetría importa. Que el total sea MAYOR que sus partes
conocidas es lo esperado cuando el catálogo no cubre todo; que sea MENOR sí es
imposible. Marcar las dos igual convierte una señal en ruido, y **un error que no
es un error entrena a no leer los errores** — que es exactamente lo que Pálpito
existe para evitar.

**Estado: arreglado.** El caso "mayor" pasó a informativo con su explicación; el
caso "menor" sigue siendo error. Éxito pasó de 10 errores a 0.

⚠️ **Junto con §7 forman la misma enfermedad por los dos lados:** allá un campo
que se escribía y nadie leía; aquí una alarma que sonaba sin que hubiera fuego.
Y hay un tercer caso el mismo día: `pasivo_total` y `pasivo_no_corriente`
existían en `modelos.py` desde siempre, pero **el importador no podía
producirlas**, así que ningún balance real cuadraba jamás. Un campo legible que
nadie puede escribir es tan inútil como uno escrito que nadie lee.
**Las tres son del mismo código, así que cuentan como UNA fuente.**

---

## 11. Una etiqueta dice lo que dice por cómo EMPIEZA, no por lo que contiene

**Fuentes independientes: 3** (Grupo Argos, Almacenes Éxito, y la taxonomía XBRL
de la Superintendencia de Sociedades — tres emisores, tres formatos distintos)

Es el cruce más fuerte que ha aparecido, porque las tres fuentes no se conocen
entre sí y las tres fallan igual.

**Grupo Argos** *(ya en §5)*: "pasivo no corriente" contiene "pasivo", y el
total de pasivos no corrientes entraba como deuda financiera. 12.492.908 contra
7.503.420 reales: **66 % de sobrestimación**.

**Almacenes Éxito, 10-sep-2026**: para que los renglones del flujo de efectivo
no se disfrazaran de resultados se prohibió toda etiqueta que contuviera
`"actividades de operacion"`. Pero bajo NIIF la utilidad operacional **se llama**
*"Ganancia por actividades de operación"*. La red atrapó al pez que debía dejar
pasar, y con ella se cayeron el margen operacional, el margen neto, el ROE, el
ROIC y la cobertura de intereses: **el 40 % del puntaje de salud** aparecía como
"sin datos" sin que nada fallara.

**La taxonomía de Supersociedades, 11-sep-2026**: al probar el diccionario del
importador contra los conceptos del portal, *"Total de patrimonio y pasivos"*
—que **es el activo total**, por el otro lado de la ecuación contable— entraba
como patrimonio por contener esa palabra. Y *"Acciones propias en cartera"*
entraba como cuentas por cobrar.

**Lo que sugiere:** buscar una frase *dentro* de una etiqueta es una heurística
que falla en las tres direcciones — de más, de menos y al revés. Lo que manda es
**de qué ES la etiqueta**, y eso se decide por dónde empieza. Un renglón que
empieza por "Ganancia" es un resultado aunque después nombre las actividades de
operación; el del flujo de caja empieza por "Efectivo neto".

⚠️ **Y hay un corolario que costó aparte:** cuando la fuente entrega un catálogo
**cerrado** —una taxonomía, no texto libre— adivinar por subcadena no solo
sobra: hace daño. Ahí se mapea por **nombre exacto**. Es la diferencia entre
`importacion.py` (PDF, etiquetas libres, hay que adivinar) y
`herramientas/supersociedades.py` (73 conceptos fijos, lista blanca).

**Estado: arreglado en los tres.** Argos por el corte perezoso de los totales;
Éxito por `_es_renglon_de_flujo`, que mira cómo empieza la etiqueta; la
taxonomía por diccionario propio de nombre exacto. Pruebas fijan **las dos
mitades** de cada uno: lo que debe entrar y lo que debe seguir fuera.

---

## 12. Un dato público puede llegar roto desde el origen, y no es culpa de quien lo lee

**Fuentes independientes: 1** (el portal datos.gov.co / Superintendencia de
Sociedades)

⚠️ **Una sola fuente.** Se anota porque la forma de fallar es nueva.

Al construir el benchmark sectorial, cuatro conceptos del estado de resultados
no empataban con el diccionario: utilidad operacional, utilidad neta, utilidad
antes de impuestos y gastos de administración. **Los cuatro que llevan tilde.**

La causa no era de este lado. La cabecera dice `charset=utf-8`, los bytes son
UTF-8 válidos, y aun así la vocal acentuada llega como `EF BF BD` — que es
**U+FFFD, el carácter de "no pude leer esto", correctamente codificado**. O sea:
el dato se deterioró antes de publicarse y el portal entrega el deterioro
intacto. `"Ganancia (p<roto>rdida) por actividades de operaci<roto>n"`.

**Lo que sugiere:** no se puede dar por hecho que una fuente oficial entregue el
texto que dice entregar, ni tratarlo como un problema de decodificación propio.
Y tampoco se puede dar por hecho que **siga** roto: si algún día lo arreglan, lo
que se escriba hoy tiene que seguir funcionando.

La salida fue comparar los dos lados por su **esqueleto ASCII** —se cae la vocal
acentuada del nuestro y el rombo del suyo, y queda la misma cadena—, que aguanta
las dos formas. Sigue siendo comparación exacta sobre la cadena entera, no por
subcadena: una prueba verifica que **ningún par de conceptos colapse al mismo
esqueleto**, que es lo único que la hace segura.

⚠️ **Es el tercer tipo de deterioro visto en una fuente**, y los tres son
distintos: el lector de PDF **pega** dos renglones *(§5, §9)*; el índice
**suplanta** cifras con números de página *(§1)*; y aquí la fuente **pierde**
caracteres. Conviene no asumir que el único enemigo es el que ya se conoce.

---

## 13. Un resumen puede perder justo aquello que se iba a medir

**Fuentes independientes: 1** (el archivo "10.000 empresas más grandes del país")

⚠️ **Una sola fuente.**

Para el benchmark sectorial había un atajo tentador: ese archivo trae ya
resumidos ingresos, ganancia, activos, pasivos y patrimonio de las 10.000
empresas más grandes, con su CIIU. Siete indicadores salían de ahí sin tocar los
19,6 millones de renglones del archivo detallado.

Se calculó, y la mediana del sector dio esto:

| | Mediana |
|---|---|
| Margen neto | **0,00 %** |
| ROA | **0,00 %** |
| ROE | **0,00 %** |

No es que el comercio de alimentos no gane plata. Es que **el archivo trae las
cifras en billones redondeadas a dos decimales**, así que a toda empresa que
gane menos de 5.000 millones se le redondea la ganancia a cero. Sirve para
ordenar por tamaño —para eso lo publican— y no sirve para nada que se divida.

**Lo que sugiere:** la precisión de un dato no es un detalle técnico, es parte
de para qué sirve. Y el modo de fallar es el peor posible: **no da error, da un
número redondo**. Una mediana de 0,00 % se ve como un dato, no como un hueco.

Es la misma enfermedad de §1 y §10 en otra forma: **un número bonito y falso**,
que es exactamente lo que Pálpito existe para no producir. La diferencia es que
esta vez la habríamos producido nosotros.

**Estado: descartado el atajo.** El benchmark se construye desde el archivo
detallado, que trae pesos exactos y además da 16 indicadores en vez de 7.
