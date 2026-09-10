# Pálpito — contexto de producto

## Qué es

Una aplicación de diagnóstico financiero que convierte estados financieros en un
juicio verificable sobre la salud de una empresa y sobre la viabilidad de sus
proyectos de inversión.

El nombre viene del capítulo 1 de Oscar León García, bibliografía del curso: *"el
logro del OBF se puede verificar a través de lo que se denominará **pálpito del
empresario** con respecto al comportamiento del flujo de caja"*. La aplicación
convierte ese pálpito en números verificables.

## El mecanismo único

**La inteligencia artificial nunca calcula.** El motor en Python calcula y decide;
el modelo recibe los números ya resueltos y solo los traduce a prosa. Cada cifra
viaja con su fórmula, sus insumos, su fuente bibliográfica y el umbral con el que
se comparó.

Ese es el diferencial frente a lo que hacen las demás herramientas del salón, que
le piden el diagnóstico directamente a un chat: aquí la IA no puede alucinar una
cifra porque nunca se le pide una cifra. El endpoint `/api/contexto-ia` muestra
literalmente el texto que se le envía al modelo, para poder auditarlo.

## Quién lo usa y dónde

Tres escenas reales, en este orden de importancia:

1. **La exposición final del curso.** Oscar proyecta la aplicación ante el
   profesor y 39 compañeros, en un salón, por videollamada de Teams, sobre un
   proyector. Tiene minutos, no horas. El profesor advirtió que *"si hay una
   cifra mal, eso les va a bajar nota"*, y pidió expresamente que la herramienta
   sea visual y "que la pongan bonita, que sea agradable".
2. **Una consultoría real a una pyme.** El profesor enmarcó todo el ejercicio
   así: llegar a empresas colombianas donde hay ignorancia en administración
   financiera y poder mostrarles dónde están sus problemas.
3. **Los propios negocios de Oscar** — Serviteca Las Vallas, el restaurante,
   Torbex, Vitalii.

En las tres escenas hay alguien **mirando por encima del hombro** a quien hay que
convencer. La aplicación no se usa en soledad: se usa para sustentar.

## Qué hace, en orden

1. **Valida** la calidad de los estados financieros antes de calcular nada. La
   validación es puerta previa, no un adorno: un diagnóstico sobre datos
   inconsistentes está mal aunque la aritmética esté bien.
2. **Calcula 26 indicadores** con trazabilidad completa.
3. **Califica la salud de 0 a 100** con la metodología a la vista.
4. **Evalúa proyectos de inversión**: VPN, TIR, TIR modificada, payback simple y
   descontado, índice de rentabilidad, flujo de caja mensual a 12 meses,
   escenarios y punto de quiebre.
5. **Dispara 11 reglas de alerta** y redacta el diagnóstico con IA.
6. **Responde preguntas** en lenguaje natural, citando siempre la fuente.

Los datos entran a mano o desde un archivo: Excel, CSV o PDF.

## Compromisos que no se negocian

- **Sin frameworks de frontend, sin build, sin Node, sin CDN.** HTML plano con
  JavaScript vanilla servido por FastAPI. Un solo contenedor. Las gráficas son
  SVG escrito a mano: el navegador solo ubica en coordenadas números que ya
  resolvió el motor.
- **Todo dato debe poder auditarse en pantalla.** Fórmula, insumos, umbral,
  fuente. El "modo docente" es la característica, no un extra.
- **Un dato faltante no vale cero.** Se excluye, se reparte su peso y se reporta.
- **Los errores del material del curso se reportan, no se ocultan.** Hay seis
  discrepancias documentadas en FORMULAS.md sección 8.
- Licencia MIT. Se evitó PyMuPDF por ser AGPL.

## Lo que distingue el tono

Honestidad antes que optimismo. El caso base tiene el balance descuadrado y la
aplicación lo detecta y lo reporta en vez de taparlo: su puntaje sale marcado
como **no confiable**. Las escalas castigan los dos extremos —una razón corriente
de 5 no saca 100, es capital ocioso—. Está documentado qué **no** es el puntaje.

Si la empresa está mal, la aplicación lo dice sin rodeos.

## Supuestos declarados

Este documento se escribió a partir del código verificado, de las transcripciones
de las sesiones 5 y 6 del curso, y del historial del proyecto. No hubo entrevista
formal con el usuario; las prioridades entre las tres escenas de uso son
inferencia del contexto, no una declaración suya.
