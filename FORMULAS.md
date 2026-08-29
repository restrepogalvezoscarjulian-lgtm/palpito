# Fórmulas y criterios adoptados

Este documento existe para que cualquiera pueda auditar los cálculos de Pálpito
sin leer el código. Cada indicador declara su fórmula, sus insumos y su fuente;
lo mismo que la aplicación muestra en pantalla al activar el **modo docente**.

Fuentes citadas:

- **Baena Toro, D. (2014).** *Análisis financiero: enfoque y proyecciones* (2ª ed.). Ecoe Ediciones.
- **García S., O. L.** *Administración financiera: fundamentos y aplicaciones*.
- **Barbosa Guerrero, L. M. (2021).** *Análisis y gerencia financiera*. Universidad El Bosque.

---

## 1. Validación previa

Antes de calcular cualquier indicador se verifica la consistencia de los datos.
Un ratio calculado sobre estados financieros inconsistentes es un número
preciso y falso.

| Verificación | Regla | Severidad |
|---|---|---|
| Ecuación contable | `Activo total = Pasivo total + Patrimonio` | error |
| Subtotales de activo | `Activo total = Activo corriente + Activo no corriente` | error |
| Partidas vs. subtotal | La suma de las partidas listadas no puede superar su subtotal | error |
| Partidas no informadas | El subtotal puede superar la suma listada (hay cuentas no reveladas) | advertencia |
| Encadenamiento del ER | Cada renglón se deriva del anterior | error |
| Valores imposibles | Cuentas que no admiten signo negativo | error |
| Datos faltantes | Indicadores que no se podrán calcular, y por qué | informativo |

El resultado es un semáforo: **rojo** si hay errores, **amarillo** si hay
advertencias, **verde** si todo cuadra.

---

## 2. Liquidez

| Indicador | Fórmula | Fuente |
|---|---|---|
| Razón corriente | `Activo corriente / Pasivo corriente` | Cartilla |
| Prueba ácida | `(Activo corriente − Inventarios) / Pasivo corriente` | Baena |
| Razón de efectivo | `Efectivo / Pasivo corriente` | Baena |
| Capital de trabajo neto contable | `Activo corriente − Pasivo corriente` | García |

> **Nota de García:** la definición contable de capital de trabajo es limitada.
> Una diferencia igual a cero no significa iliquidez, sino *mayor riesgo* de
> iliquidez. La medida operativa correcta es el KTNO.

---

## 3. Actividad

| Indicador | Fórmula | Fuente |
|---|---|---|
| Días de cartera | `365 / (Ventas a crédito / Cuentas por cobrar)` | Cartilla |
| Días de inventario | `365 / (Costo de ventas / Inventarios)` | Cartilla |
| Días de proveedores | `365 / (Compras / Proveedores)` | Cartilla |
| Ciclo de conversión de efectivo | `Días cartera + Días inventario − Días proveedores` | García |
| **KTNO** | `Cuentas por cobrar + Inventarios − Proveedores` | García |
| **PKT** | `KTNO / Ventas` | García |
| Rotación de activos | `Ventas / Activo total` | Baena |

### Aproximaciones declaradas

Cuando el caso no informa **ventas a crédito**, se usan las ventas totales.
Cuando no informa **compras del período**, se usa el costo de ventas.
En ambos casos la aplicación lo advierte explícitamente en el indicador y en la
sección de calidad de datos. No se estima en silencio.

---

## 4. Endeudamiento

| Indicador | Fórmula | Fuente |
|---|---|---|
| Nivel de endeudamiento (informado) | `Pasivo total / Activo total` | Baena |
| Nivel de endeudamiento (implícito) | `(Activo total − Patrimonio) / Activo total` | Baena |
| Apalancamiento | `Pasivo total / Patrimonio` | Cartilla |
| Multiplicador del patrimonio | `Activo total / Patrimonio` | Cartilla |
| Cobertura de intereses | `UAII / Gastos financieros` | García |
| Costo implícito de la deuda | `Gastos financieros / Deuda financiera promedio` | García |

### Por qué dos medidas de endeudamiento

La cartilla del curso presenta `Pasivo / Patrimonio` y
`Pasivo / (Activo − Pasivo)` como si fueran equivalentes. Solo lo son si el
balance cuadra exactamente.

Pálpito calcula el nivel de endeudamiento por dos vías:

- **Informado** — con el pasivo que el usuario reportó.
- **Implícito** — forzando el cuadre: `Activo − Patrimonio`.

Si ambas difieren, es porque hay pasivos no revelados, y **esa diferencia es un
diagnóstico en sí misma**. En el caso Comercial Andina S.A. la brecha es de
casi 6 puntos porcentuales en 2024 (55,75% informado contra 61,43% implícito).

El costo implícito de la deuda se calcula sobre el **saldo promedio** del
período, no sobre el saldo final, porque los intereses se causan a lo largo del
año. Solo se puede calcular desde el segundo período.

---

## 5. Rentabilidad y valor

| Indicador | Fórmula | Fuente |
|---|---|---|
| Margen bruto | `Utilidad bruta / Ventas` | Baena |
| Margen operacional | `Utilidad operacional / Ventas` | Baena |
| Margen neto | `Utilidad neta / Ventas` | Baena |
| **ROA** | `Utilidad operacional (UAII) / Activo total` | Cartilla |
| **ROE** | `Utilidad neta / Patrimonio` | Cartilla |
| Tasa efectiva de impuestos | `Impuestos / Utilidad antes de impuestos` | Baena |
| **UODI** | `UAII × (1 − tasa de impuestos)` | Cartilla |
| Capital invertido | `KTNO + Propiedad, planta y equipo` | García |
| **ROIC** | `UODI / Capital invertido` | García |

### DuPont

```
ROE = (Utilidad neta / Ventas) × (Ventas / Activo total) × (Activo total / Patrimonio)
        margen neto              rotación de activos        multiplicador del patrimonio
```

La aplicación calcula la variación de cada factor entre períodos para atribuir
el cambio del ROE a su causa: margen (precios y costos), rotación (eficiencia
en activos) o apalancamiento (estructura de financiación).

Hay una prueba automatizada (`test_dupont_reconstruye_el_roe`) que verifica que
el producto de los tres factores dé exactamente el ROE calculado por separado.

---

## 6. Puente de caja (García)

```
    UODI
  − Aumento del KTNO
  − Inversión en activos fijos
  ─────────────────────────────
  = Flujo de caja libre
```

Responde la pregunta que un ratio no responde: *¿por qué vendí más y tengo
menos plata?* Se contrasta contra la variación real de la deuda financiera y
del efectivo para mostrar cómo se cubrió el faltante.

**Limitación declarada:** sin el dato de depreciación no se puede sumar al flujo
de caja bruto ni separar el CAPEX de reposición del de crecimiento. La
aplicación marca el resultado como aproximación y explica por qué. **Nunca
estima la depreciación.**

---

## 7. Puntaje de salud financiera (0-100)

Un puntaje único es cómodo de leer y fácil de manipular. Por eso aquí no se
esconde nada: la aplicación muestra en pantalla, junto a cada nota, el umbral
con el que se comparó, de dónde salió ese umbral y en qué punto exacto de la
escala cayó la empresa. Quien no esté de acuerdo con un criterio puede señalar
exactamente cuál, en vez de discutir el número entero.

### 7.1 Cómo se arma cada nota

```
  nota del indicador = 70% × nivel + 30% × tendencia
```

- **Nivel** — qué tan cerca está el valor del último periodo de un rango
  considerado sano por la bibliografía. Se **interpola linealmente** entre los
  puntos de la escala, para que no haya saltos arbitrarios: una razón corriente
  de 1,49 no puede sacar 40 y una de 1,51 sacar 85. Fuera de los extremos la
  escala se aplana, nunca extrapola.
- **Tendencia** — si mejoró o empeoró entre el primer periodo y el último,
  medida en variación relativa y orientada según lo deseable en cada caso: en
  el ciclo de caja y en el endeudamiento, **bajar es mejorar**.

Se separan a propósito. Una empresa puede estar en buen nivel y deteriorándose,
o mal parada y recuperándose, y las dos cosas importan. Si un indicador solo
tiene un dato útil, se califica **solo por nivel**: no se inventa una tendencia
comparando el valor consigo mismo.

### 7.2 Ponderaciones

| Dimensión | Peso | Indicadores (peso dentro de la dimensión) |
|---|---|---|
| Liquidez | 15% | Razón corriente (60), prueba ácida (40) |
| Actividad | 20% | Ciclo de caja (45), PKT (30), rotación de activos (25) |
| Endeudamiento | 25% | Cobertura de intereses (55), nivel de endeudamiento (45) |
| Rentabilidad | 25% | Margen operacional (35), ROE (35), margen neto (30) |
| Generación de valor | 15% | ROIC menos costo de la deuda (100) |

Endeudamiento y rentabilidad pesan más porque son las dos preguntas que decide
un socio: *¿esto rinde?* y *¿aguanta?* La generación de valor va aparte porque
mide algo que ninguna de las otras contesta: si el negocio rinde más de lo que
cuesta la plata que lo financia.

### 7.3 Umbrales y su origen

Los umbrales salen de la bibliografía del curso. Donde la bibliografía da un
rango y no un punto, la escala premia el centro del rango y **castiga los dos
extremos**: una razón corriente de 5 no es salud perfecta, es capital ocioso, y
un endeudamiento de cero desaprovecha el apalancamiento. Cada escala completa
viaja en la respuesta de la API y se dibuja en la interfaz.

### 7.4 Datos faltantes

Un criterio sin datos **no puntúa cero**: se excluye y su peso se reparte entre
los que sí tienen dato dentro de su dimensión; si la dimensión entera queda sin
datos, su peso se reparte entre las demás. Contar cero confundiría *no
informado* con *malo*. Todo lo excluido se reporta en pantalla.

### 7.5 La validación sigue siendo puerta previa

Si el semáforo de calidad de datos está en rojo, el puntaje se calcula igual
pero llega marcado como **no confiable**, con la advertencia encima. Es el caso
de Comercial Andina: el balance no cuadra, así que el 58,9 sirve para ubicar el
orden de magnitud, no para decidir.

### 7.6 Qué no es este puntaje

No es una calificación de riesgo crediticio ni un modelo estadístico validado
contra empresas quebradas (Altman, Ohlson y similares). Es una **ponderación
declarada de indicadores del curso**, útil para ordenar la conversación y
comparar escenarios dentro de la misma empresa. Comparar el puntaje entre
empresas de sectores distintos exigiría umbrales sectoriales que esta
aplicación no tiene.

---

## 8. Discrepancias con la cartilla del curso

Pálpito calcula correctamente y documenta aquí las diferencias. No es una
crítica al material: es el criterio adoptado, declarado de forma auditable.

### 8.1 ROA invertido

La cartilla del Módulo 1 (p. 28) enuncia la fórmula correctamente
—beneficio antes de intereses e impuestos sobre activos totales— pero en el
ejemplo calcula `$100.000.000 / $10.000.000 = 10%`, que es activos sobre
beneficio. El resultado coincide con el correcto solo porque las cifras son
redondas.

**Criterio adoptado:** `UAII / Activo total`.

### 8.2 GAF con resultado inconsistente

La cartilla del Módulo 2 (p. 21) plantea:

```
GAF = UAII / [UAII − Intereses − (Dividendos / (1 − t))]
```

y reporta `42.000.000 / 32.000.000,83 = 1,3`. Pero con su propia fórmula el
denominador es `42 − 10 − (8 / 0,7) = 20.571.429`, lo que da **GAF = 2,04**.
El valor 32.000.000 es la utilidad antes de impuestos, no el denominador.
El error se propaga al GAT: la cartilla reporta 3,12 cuando corresponde 4,90.

### 8.3 Datos inconsistentes en el ejemplo de DuPont

En el ejemplo del Módulo 2 (p. 7), Activo (200 M) ≠ Pasivo (80 M) +
Patrimonio (110 M). Y la utilidad reportada (90 M) no se deriva de
ventas (400) − costos (235) − gastos (105) = 60 M.

Este es precisamente el tipo de inconsistencia que el módulo de validación de
Pálpito detecta automáticamente.

### 8.4 Precio de venta inconsistente en punto de equilibrio

En el ejemplo del Módulo 2, el enunciado indica un precio de $125.000, pero las
figuras 10 y 11 muestran $175.000. El resultado final (96 unidades) corresponde
a $125.000, que es el correcto.

### 8.5 Signos en el estado de resultados

Las figuras 17 y 18 del Módulo 1 muestran `+ Gastos administrativos` y
`+ Gastos de ventas` cuando en realidad se restan. Es cosmético en una hoja de
cálculo, pero traducido literalmente a código sumaría los gastos.

---

## 9. Indicadores pendientes

Requieren datos que el caso base no informa. Están en el alcance del curso y se
agregarán cuando lleguen casos que los soporten:

| Indicador | Dato faltante |
|---|---|
| EBITDA | Depreciación y amortización |
| GAO / GAF / GAT | Costos fijos y variables separados, dividendos |
| Punto de equilibrio | Precio unitario, costo variable unitario, costos fijos |
| WACC | Costo del patrimonio (Ke), estructura objetivo |
| EVA | WACC |
| Flujo de caja libre exacto | Depreciación, CAPEX de reposición vs. crecimiento |
