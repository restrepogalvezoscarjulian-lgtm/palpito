# Cruces vistos

Coincidencias entre fuentes que no se conocen entre sí. Se anotan en el momento
en que aparecen, con su origen, porque a la semana ya no se puede verificar de
dónde salieron.

**Cómo se cuentan las fuentes:** dos cosas del mismo autor son **una** fuente.
Coinciden porque piensa igual, no porque la idea se sostenga sola.

---

## 1. En un estado financiero publicado hay números que no son cifras contables

**Fuentes independientes: 2** (dos emisoras distintas, dos documentos distintos)

- **Ecopetrol**, informe consolidado 2024: la tabla de contenido tiene la misma
  forma que un estado financiero —concepto a la izquierda, número a la derecha—
  pero ese número es **una página**. Produjo `Propiedades, planta y equipo = 63`.
- **Nutresa**, informe consolidado 2025: la primera columna de cada renglón es
  **el número de nota**: `Inventarios | 11 | 2.558.764 | 2.447.873`. Con dos
  periodos se guardaba `[11, 2.558.764]`.

**La regla que sale:** en un documento financiero, un número pequeño y aislado
junto a un concepto **casi nunca es un saldo**. Es una página, una nota o un
año. La cifra contable es la que está en la cola del renglón y tiene separador
de miles.

**Estado: comprobado.** Los dos casos se reprodujeron con el archivo real y hay
pruebas que los fijan (`test_empresa_grande.py`).

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
