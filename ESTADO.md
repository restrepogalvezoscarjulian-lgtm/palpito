# Estado — 29 de agosto de 2026

## Dónde vamos

**Pálpito** es una aplicación de diagnóstico financiero construida para la
asignatura *Análisis y Gerencia Financiera* (Universidad El Bosque). Está
**terminada y funcionando**, publicada en GitHub y corriendo en local.

Verificado hoy, no de memoria:

- `71 passed in 0.52s` — la suite completa de pruebas
- Commit `4db8698` en `main`, sin cambios pendientes
- Publicada en <https://github.com/restrepogalvezoscarjulian-lgtm/palpito> (MIT)
- Servidor local responde `{"estado":"ok","version":"0.3.0","ia":{"disponible":true}}`

Lo que hace: valida la calidad de los estados financieros → calcula 26
indicadores con trazabilidad → dispara 11 reglas de alerta → una IA redacta el
diagnóstico y responde preguntas. **Cinco bloques de trabajo, los cinco cerrados.**

---

## Lo primero al retomar

🔴 **Quedan tres huecos identificados, en este orden de valor por esfuerzo:**

**1 · Gráficas** (lo más rentable)
Hoy todo son tablas y números. Faltan dos o tres gráficas: evolución de
márgenes, composición del ciclo de caja, DuPont. Sube mucho el impacto visual
con poco esfuerzo. Van en `frontend/index.html`, sin librerías externas o con
una desde CDN.

**2 · Puntaje de salud financiera (0-100)**
La propuesta original (de ChatGPT) incluía un tablero tipo `Salud: 78/100` con
puntaje por dimensión. **No se construyó** porque un score sin metodología
justificada es indefendible ante el profesor. La forma correcta de hacerlo:
ponderaciones **visibles en pantalla**, con la fórmula al lado, para que se
pueda auditar. Iría en `backend/motor/` como módulo nuevo.

**3 · Cargar archivos Excel / PDF** (lo más costoso)
Hoy los datos entran por el editor manual de la interfaz o por un JSON en
`casos/`. Si el próximo caso llega en Excel, toca digitarlo. **Ojo: esto es una
trampa de tiempo**, por eso se aplazó deliberadamente. No empezar por aquí.

**Para arrancar el servidor:**
```bash
cd palpito/backend
uvicorn api:app --reload      # → http://localhost:8000
python -m pytest -q           # deben pasar 71
```

---

## Lo que se decidió, y por qué

**La IA nunca calcula, solo redacta.**
Es la decisión de arquitectura central. El motor (Python) calcula y decide; el
modelo recibe los números ya resueltos y solo los traduce a prosa. Por eso no
puede alucinar. Verificado en real: de 22 cifras citadas por el modelo, 22
existían en el contexto. Cero inventadas. Hay un endpoint `/api/contexto-ia`
que muestra exactamente qué recibe el modelo, para poder auditarlo.

**Las pruebas son el entregable, no un accesorio.**
El paso 4 del taller pide "verificar manualmente al menos 4 cálculos". En vez de
hacerlo a mano, cada fórmula tiene una prueba con el cálculo escrito en el
docstring. Es un argumento mucho más fuerte en la sustentación.

**Se calcula bien aunque la cartilla del curso esté mal.**
Se encontraron 5 errores en el material del curso (ROA invertido, GAF con
resultado inconsistente, datos que no cuadran en el ejemplo de DuPont, precio
inconsistente en punto de equilibrio, signos invertidos en el estado de
resultados). Están documentados en `FORMULAS.md` como *criterio adoptado*, no
como crítica. **Decisión de Oscar: se reportan, no se ocultan.**

**El caso base tiene el balance descuadrado y eso es una funcionalidad.**
Comercial Andina S.A. no cuadra por 550 (2023) y 390 (2024) millones. La app lo
detecta sola y reporta el endeudamiento por dos vías: informado (55,75%) e
implícito (61,43%). La diferencia *es* el diagnóstico.

**Un solo contenedor, sin frameworks de frontend.**
FastAPI calcula y sirve la interfaz. HTML plano con JavaScript vanilla. Sin
build, sin Node, sin dependencias que se pudran en seis meses.

**Despliegue aplazado a propósito.**
Todo está listo para publicar en `finanzas.torbex.com.co` (DNS ya registrado en
Namecheap, guía escrita en `docs/DESPLIEGUE.md`), pero Oscar decidió dejarlo en
local por ahora y atacar primero los huecos.

---

## Las trampas

🔴 **El Dockerfile NUNCA se ha construido.** No hay Docker instalado en el PC.
La imagen se armará por primera vez en el servidor. Si falla, será en ese primer
*Deploy*, y Dokploy muestra el log completo.

🔴 **En Dokploy: usar tipo "Application", NO "Compose".** Está documentado en la
guía maestra de infraestructura de Vitalii: los servicios Compose se salen de
`dokploy-network` en **cada** redespliegue y hay que reconectarlos a mano con
`docker network connect`. Los Application se unen solos.

🔴 **Al generar JavaScript desde scripts de Python, cuidado con `\n`.**
Ya pasó una vez: un `\n` dentro de un string no-raw se convirtió en salto de
línea real y rompió una expresión regular en `frontend/index.html`. Si se vuelve
a editar el frontend con scripts, usar strings raw (`r"..."`) o verificar el
archivo generado.

🔴 **VS Code bloquea la carpeta.** Renombrar o mover el directorio del proyecto
falla con "Permission denied" mientras VS Code lo tenga abierto. Solución que
funcionó: `robocopy` a la carpeta nueva y luego borrar la vieja.

🔴 **Rutas con `:` en Git Bash de Windows.** `git show origin/main:.env.example`
falla porque convierte la ruta. Usar `MSYS_NO_PATHCONV=1` adelante.

**La credencial de GitHub se cambió hoy.** Había una llave vieja
(`x-access-token`) con permiso solo de lectura, que daba 403 al hacer push. Se
borró y se re-autenticó por navegador. Si otro proyecto que use git con GitHub
pide iniciar sesión, es por esto. Es normal, se resuelve con un clic.

**La clave de OpenRouter vive solo en `palpito/.env`**, que está en
`.gitignore`. Verificado: NO está en GitHub. `.env.example` sí se subió, vacío.
Modelo actual: `deepseek/deepseek-v4-flash` (~USD 0,00004 por diagnóstico).
Se puede cambiar a `deepseek/deepseek-v4-pro` editando una línea del `.env`.

---

## 🔴 Pendientes que son de Oscar, no míos

- **¿Cuándo desplegar en `finanzas.torbex.com.co`?** Todo está listo. Él decidió
  dejarlo en local por ahora. No desplegar sin que lo pida.

- **¿Se le regala el repositorio al profesor, y cómo?** La idea era entregárselo
  como proyecto open source. Ya está público con licencia MIT a nombre de Oscar,
  pero **no se ha definido cómo ni cuándo se le entrega**.

- **¿Los tres huecos se atacan todos, o solo alguno?** Mi recomendación es
  gráficas primero, puntaje después, carga de archivos al final (o nunca, si el
  tiempo aprieta). Falta su palabra.

- **¿Qué exige la rúbrica de calificación?** Nunca se supo con qué lo califican
  ni cuál es el entregable formal esperado. La app excede lo que pide el taller,
  pero convendría confirmar que no falta algo puntual.

- **¿Los casos futuros vendrán en Excel?** Si el profesor los manda en Excel, la
  prioridad del hueco #3 sube mucho. Hoy es una suposición, no un dato.

---

## Contexto que un chat nuevo no puede deducir

**Origen del nombre.** Viene del capítulo 1 de Oscar León García, bibliografía
del curso: *"el logro del OBF se puede verificar a través de lo que se
denominará **pálpito del empresario** con respecto al comportamiento del flujo
de caja"*. La app convierte ese pálpito en números verificables. Está como
epígrafe en la cabecera de la interfaz.

**De dónde salieron las funcionalidades.** Se estudiaron dos aplicaciones:
- *Syft Analytics* → de ahí salió el módulo de **calidad de datos** (su función
  "Review"), que resultó ser lo más valioso.
- *Fireflies.ai* → de ahí salió el patrón **"preguntar en lenguaje natural y
  citar la fuente"** (su función AskFred).

Lo demás es propio: la validación como puerta previa, el endeudamiento por
partida doble, el modo docente, el puente de caja de García, la arquitectura
"la IA no calcula" y el editor de escenarios.

**Estructura del proyecto:**
```
palpito/
├── backend/motor/     modelos · validacion · indicadores · diagnostico · narrativa
├── backend/tests/     71 pruebas
├── backend/api.py     FastAPI: calcula y sirve la interfaz
├── frontend/          index.html, sin frameworks
├── casos/             comercial_andina.json
├── docs/DESPLIEGUE.md guía paso a paso para Dokploy
├── FORMULAS.md        fórmulas, fuentes y los 5 errores de la cartilla
└── .env               🔴 la clave (NO se sube a git)
```
