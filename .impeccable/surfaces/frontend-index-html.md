---
version: 1
slug: "frontend-index-html"
primary_target: "frontend/index.html"
related_targets: []
---

## Direction contract

THESIS: La empresa se lee como el registro continuo de un instrumento de
precisión, no como una cuadrícula de tarjetas. Refusa el dashboard de fichas
iguales con número grande y etiqueta pequeña.

OWN-WORLD: Retícula milimetrada tenue sobre grafito azulado; trazo de aguja
entintada en ámbar cálido, tinta roja para lo adverso y verde fósforo apagado
para lo favorable; nunca neón frío. Tipografía de una familia con cifras
tabulares; negativos entre paréntesis; doble raya bajo los totales. Notas al pie
numeradas como sistema de trazabilidad — donación de disciplina de la dirección
del dictamen. Escalas calibradas con marca de dónde cayó la empresa.

STORY: Quien mira entiende en cinco segundos si la empresa está bien, y puede
abrir cualquier cifra hasta su fórmula y su fuente sin salir de la pantalla.

FIRST VIEWPORT: Cabecera fija delgada con el nombre de la empresa y el estado.
Debajo, a ancho completo, el registro: el dictamen a la izquierda con su nota de
confiabilidad, la aguja del puntaje a la derecha sobre su escala calibrada. Sin
tarjeta contenedora. La acción primaria (cargar archivo) vive en la cabecera.

FORM: Instrumento de registro de precisión, candidato 5 de la lista ordenada,
elegido por el usuario por encima del asignado. Seed b6331660.

FINISH: unreviewed and undocumented is unfinished; this build ends with the
finish review, the verdict, DESIGN.md, and every shipping raster carrying its
provenance.

## Escena y modo

Modo Operate. Tres escenas, en orden: exposición proyectada ante profesor y 39
compañeros por Teams; consultoría a una pyme; uso propio.

La escena fuerza una decisión: un proyector de salón lava los negros. Por eso el
instrumento tiene dos calibraciones — oscura por defecto (pantalla, Teams) y
clara de alto contraste (proyector), conmutables. No es un dark mode decorativo:
es una función de la escena de uso.

## Restricciones duras

Sin frameworks, sin build, sin Node, sin CDN. HTML plano y JavaScript vanilla
servido por FastAPI. Gráficas en SVG escrito a mano. Toda cifra auditable en
pantalla.
