# Sistema visual de Pálpito

Escrito **desde lo construido**, no antes de construirlo. Describe el mundo que
quedó en `frontend/index.html`, que es un solo archivo sin build, sin Node y sin
CDN.

## La idea

La empresa se lee como **el registro continuo de un instrumento de precisión**:
retícula milimetrada, escalas calibradas con marcas, agujas que señalan dónde
cayó un valor. Lo que se rechaza es la cuadrícula de tarjetas iguales con número
grande y etiqueta pequeña, que es a donde llega por defecto cualquier panel
financiero.

De la lectura descartada —el informe auditado— se conservó una disciplina: el
veredicto se emite como **dictamen** y cada cifra puede abrirse hasta su fórmula
y su fuente, como las notas al pie de un estado financiero.

## Las dos calibraciones

No es un modo oscuro decorativo: es una función de la escena de uso.

| Calibración | Cuándo | Cómo |
|---|---|---|
| **Pantalla** (por defecto) | Trabajo diario, Teams | Grafito azulado `#0d1219` |
| **Proyector** | Exponer en un salón | Claro `#f4f6f9`, alto contraste |

Un proyector de salón lava los negros: en esa escena la calibración clara no es
una preferencia, es la que se lee. El botón vive al pie de la barra lateral y la
elección se recuerda en `localStorage`, dentro de `try/catch` porque en modo
privado lanza.

Todo el tema son variables CSS sobre `html[data-cal="proyector"]`. Ningún color
se define solo dentro de ese bloque: la paleta clara redefine tokens que ya
existen en `:root`.

## Paleta

Tintas de instrumento: **cálidas y entintadas, nunca neón frío**.

| Token | Pantalla | Papel |
|---|---|---|
| `--fondo` | `#0d1219` | `#f4f6f9` |
| `--panel` | `#141b25` | `#ffffff` |
| `--aguja` | `#e8a33d` | `#a35f07` |
| `--tinta-mal` | `#e8615a` | `#b3261e` |
| `--tinta-bien` | `#5cb98a` | `#1d6b47` |
| `--tinta-ojo` | `#d9a441` | `#8a5a06` |

Estrategia: **restringida** — neutros más una tinta de acento, que es el piso
para una superficie donde el visitante viene a operar.

## Tipografía

Una sola familia (pila del sistema) más una monoespaciada para cifras. Escala
**fija en rem**, razón ~1,2, de `--t-micro` (10,5px) a `--t-gran` (26px). Nada
fluido: el usuario mira a un DPI constante y un título que encoge se ve peor.

Regla que no se negocia: **todas las cifras son tabulares**
(`font-variant-numeric: tabular-nums`). Una columna de números que no alinea es
una tabla que no se puede auditar.

Convenciones tomadas de los estados financieros:
- Negativos **entre paréntesis**, no con signo menos.
- **Doble raya** bajo los totales (`border-bottom: 3px double`).

## La retícula

El papel milimetrado **no es un tapiz**: aparece solo bajo la zona de medición
—el dictamen— y se desvanece a los lados con una máscara.

Vive en un pseudo-elemento `::before`, no en el elemento. Enmascarar el elemento
entero desvanece también su texto; ese error se cometió y se corrigió.

## Profundidad

Se eligió **el borde, no la elevación**. Un instrumento tiene bordes de chasis,
no sombras flotantes. Las tarjetas llevan `1px solid var(--borde)` y ninguna
sombra ancha; la sombra queda reservada para lo que de verdad flota sobre la
página (los tooltips).

## Navegación por módulos

La aplicación era una sola página larga. Al exponer eso cuesta caro: el orden de
la presentación lo imponía el scroll y no quien habla, y llegar al módulo de
proyecto exigía pasar por todo el diagnóstico.

Siete módulos en una barra lateral fija: Dictamen, Salud financiera,
Indicadores, Diagnóstico, Panorama visual, Benchmark sectorial y Proyecto de
inversión. Cada uno agrupa secciones que ya existían; **ninguna cambió por
dentro**.

- El módulo activo se marca con **una aguja de 2px en el margen**, no con un
  borde grueso ni un fondo saturado.
- Cada entrada lleva su nombre y una línea de qué contiene: la barra explica la
  aplicación, no solo navega.
- El módulo se recuerda en `localStorage` y se refleja en el hash, así que
  recargar o compartir el enlace cae en el mismo sitio.
- Bajo 900px la barra se convierte en un panel deslizable con botón *Módulos*.

## Impresión

`Imprimir / PDF` no imprime lo que está en pantalla: **arma los siete módulos**,
imprime y devuelve la pantalla al módulo donde estaba. Un PDF con un solo
módulo estaría incompleto.

El papel es blanco, así que la hoja de impresión redefine la paleta completa
sin importar la calibración de pantalla: fondo blanco, tintas oscuras, retícula
fuera, barra lateral y controles fuera. Cada módulo abre página (`break-before`)
y las filas de tabla no se parten.

El **modo docente se imprime siempre**, aunque esté apagado en pantalla: en
papel no hay tooltips ni hover, y la fórmula con su fuente es lo que permite
auditar el informe fuera de la aplicación. El pie lleva empresa, periodos,
moneda y fecha de generación.

## Benchmark

La columna *Sector* es un campo editable vacío por defecto: **el motor no
rellena ninguna referencia**. Cada indicador muestra bajo su nombre si "mayor es
mejor" o "menor es mejor", que es lo que hace legible el signo de la brecha.

Las referencias se guardan por navegador y se recalculan 400 ms después de que
la persona deja de escribir; solo se repintan las celdas de brecha y lectura,
para no robarle el foco al campo que está digitando.

## Componentes propios

**El medidor** (`medidorPuntaje`) — arco de 180° con marcas cada 10 puntos, más
largas cada 25. El valor se marca **sobre el arco**, no con una aguja desde el
centro: así el centro queda libre para la cifra, que es lo que se lee desde el
fondo de un salón. La primera versión sí tenía aguja y atravesaba el número.

**Los tooltips** (`marcaAyuda` / `.globo`) — el contenido **no se escribe en el
frontend**: sale del motor, que ya carga la interpretación, la fórmula y la
fuente de cada indicador. Un texto duplicado se desincroniza. Se posicionan
midiendo el globo ya renderizado, así que nunca se salen de la pantalla.
Responden a hover, a foco de teclado y a toque, y se cierran con `Escape`.

**El dictamen del proyecto** — la marca de veredicto es un SVG dibujado, no un
emoji ni un glifo.

**El marcador del benchmark** — pastillas con el conteo de indicadores mejor, en
línea y peor que el sector, más los que no tienen referencia. Los que faltan se
cuentan y se muestran: un marcador que solo dijera "4 mejor" escondería que hay
14 sin comparar.

## Superficies del navegador

Lo que no se dibuja también lleva el diseño: `::selection`, la barra de
desplazamiento, `accent-color`, el anillo de foco (`:focus-visible`, 2px de
`--aguja`) y el desplazamiento del subrayado de los enlaces.

## Movimiento

Poco y con propósito: el arco del medidor y las barras de dimensión se llenan en
900 ms con salida exponencial; los tooltips entran en 140 ms. Todo se apaga bajo
`prefers-reduced-motion`.

## Responsivo

Dos cortes: 900px (la barra lateral pasa a panel deslizable con botón
*Módulos*) y 560px (todo a una columna). Verificado por medición y no por
captura: a 380px de viewport, `scrollWidth == clientWidth` y la barra queda
fuera de pantalla. Solo las tablas superan el ancho, cada
una dentro de su propio `.desplazable` con `overflow-x: auto`.

Nota de método: Chrome headless en Windows impone un ancho mínimo de ventana
(~490px), así que una captura pedida a 390px es una página de 490px recortada y
**miente**. Para medir de verdad hay que cargar la página en un iframe del ancho
buscado.

## Lo que este sistema rechaza

- Numeración de secciones (01/02/03): se quitó al insertar el módulo de proyecto
  en medio, porque la secuencia ya no informaba nada.
- Emojis como sistema de iconos.
- Bordes de color gruesos a la izquierda de las tarjetas.
- Texto con degradado.
- Vidrio y desenfoque como decoración; `backdrop-filter` solo está en la
  cabecera fija, donde hay contenido pasando por debajo.

## Deuda conocida

El detector de la skill marca la retícula como *decorative grid background*. Se
mantiene a propósito: el propio detector exceptúa las superficies de medición, y
aquí la retícula está confinada a la zona del dictamen y es el material central
de la dirección elegida.
