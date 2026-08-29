# Pálpito

**Diagnóstico financiero para quien no es contador.**

Sube un balance y un estado de resultados; Pálpito calcula los indicadores,
detecta si los datos son confiables, explica **por qué** la empresa está como
está y responde preguntas en lenguaje corriente.

> «El logro del objetivo básico financiero se puede verificar a través de lo que
> se denominará **pálpito del empresario** con respecto al comportamiento del
> flujo de caja.»
> — Oscar León García, *Administración Financiera: Fundamentos y Aplicaciones*

García explica que el tendero de barrio no lleva contabilidad, pero *sabe* si su
negocio va bien porque siente la caja. Esta aplicación convierte ese pálpito en
números verificables.

---

## El principio de diseño

**La inteligencia artificial nunca calcula. Solo redacta.**

```
   Datos  →  Validación  →  Motor de cálculo  →  Reglas  →  IA
            ¿cuadra?       26 indicadores      alertas    prosa
            (Python)       (Python)            (Python)   (LLM)
```

Los cuatro primeros pasos son código determinista: mismas entradas, mismas
salidas, verificado por 71 pruebas automatizadas. El modelo de lenguaje recibe
los números ya calculados y su único trabajo es traducirlos a lenguaje que un
empresario entienda.

Consecuencias prácticas:

- No puede equivocarse en una división.
- No puede inventar un indicador que no exista.
- Si un dato falta, dice *"no disponible"* y explica cuál haría falta. No lo estima.
- **Si la IA no está configurada, la aplicación funciona completa.** Solo pierde
  el párrafo en prosa.

El endpoint `/api/contexto-ia` muestra el texto exacto que se le envía al
modelo, para que cualquiera pueda auditar que no recibe nada que el motor no
haya calculado antes.

---

## Qué hace

### 1. Verifica la calidad de los datos antes de calcular

Un ratio sobre estados financieros inconsistentes es un número preciso y falso.
Pálpito revisa primero la ecuación contable, los subtotales, el encadenamiento
del estado de resultados y los valores imposibles.

En el caso de ejemplo detecta que el balance **no cuadra** por 550 y 390
millones, y advierte que el nivel de endeudamiento calculado queda subestimado
en casi 6 puntos.

### 2. Calcula 26 indicadores con trazabilidad completa

Liquidez · Actividad · Endeudamiento · Rentabilidad · Valor.

Cada indicador expone su fórmula, sus insumos y su fuente bibliográfica. El
**modo docente** los muestra en pantalla. Ver [FORMULAS.md](FORMULAS.md).

### 3. Explica el puente de caja

La pantalla que responde *"¿por qué vendí más y tengo menos plata?"*:

```
UODI generada por la operación                     1.057
− Consumido por el aumento del KTNO                 −670
− Consumido por inversión en activos fijos          −450
──────────────────────────────────────────────────────────
Flujo de caja libre aproximado                       −63

Se cubrió con más deuda financiera                  +770
Y con el efectivo que había en caja                 −140
```

### 4. Prioriza alertas con reglas explícitas

Once reglas auditables, cada una citando la evidencia numérica que la disparó.
Sin IA de por medio.

### 5. Permite simular escenarios

Edita cualquier cifra y recalcula. En el caso de ejemplo, bajar la cartera de
1.680 a 1.200 convierte el flujo de caja libre de −63 a +417 y desactiva dos
alertas.

### 6. Responde preguntas sobre tus datos

> **—¿Por qué tengo menos plata si vendí más?**
>
> Sus ventas crecieron 19,10%, pero el costo de ventas subió 22,61%… su cartera
> creció 34,40% y sus inventarios 32,73%, mucho más rápido que las ventas.
>
> `Fuentes: UODI 1.057 · KTNO −670 · Activos fijos −450 · FCL −63 · Deuda +770 · Efectivo −140`

Cada respuesta cierra con las cifras exactas en las que se apoyó.

---

## Instalación

### Con Docker

```bash
git clone https://github.com/restrepogalvezoscarjulian-lgtm/palpito.git
cd palpito
cp .env.example .env      # opcional: agrega tu clave de OpenRouter
docker compose up --build
```

### Con Python

```bash
cd backend
pip install -r requirements.txt
uvicorn api:app --reload
```

En ambos casos: <http://localhost:8000>

### Configuración

Copia `.env.example` como `.env`:

```ini
OPENROUTER_API_KEY=sk-or-v1-...          # opcional
OPENROUTER_MODELO=deepseek/deepseek-v4-flash
```

Sin clave, la aplicación funciona completa; solo se desactiva la redacción en
prosa. Con `deepseek-v4-flash` cada diagnóstico cuesta alrededor de
**USD 0,00004**.

---

## Pruebas

```bash
cd backend
python -m pytest -v
```

```
71 passed
```

La suite verifica cada fórmula contra un valor calculado a mano, con el cálculo
escrito en el docstring:

```python
def test_razon_corriente(ind):
    """2950/1650 = 1.7879 ; 3620/2050 = 1.7659"""
```

Incluye un control negativo (`test_empresa_sana_no_dispara_alertas_criticas`):
un caso ficticio con buenos números que confirma que el motor se calla cuando
debe callarse. Y pruebas de la capa de IA que **no gastan créditos**: la llamada
a OpenRouter se simula.

---

## Estructura

```
palpito/
├── backend/
│   ├── motor/
│   │   ├── modelos.py       estructuras de datos
│   │   ├── validacion.py    calidad de los datos
│   │   ├── indicadores.py   26 indicadores + DuPont + puente de caja
│   │   ├── diagnostico.py   motor de reglas → alertas
│   │   └── narrativa.py     única pieza que habla con el modelo
│   ├── tests/               71 pruebas
│   └── api.py               FastAPI: calcula y sirve la interfaz
├── frontend/index.html      interfaz, sin frameworks
├── casos/                   casos de ejemplo
├── docs/DESPLIEGUE.md       guía de despliegue
└── FORMULAS.md              fórmulas, fuentes y criterios adoptados
```

---

## API

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/salud` | Estado del servicio y de la IA |
| `GET` | `/api/casos` | Casos de ejemplo disponibles |
| `GET` | `/api/casos/{id}` | Datos crudos de un caso |
| `GET` | `/api/casos/{id}/analisis` | Análisis completo |
| `POST` | `/api/analizar` | Analiza estados financieros propios |
| `POST` | `/api/narrar` | Diagnóstico redactado por IA |
| `POST` | `/api/preguntar` | Pregunta libre sobre los datos |
| `GET` | `/api/contexto-ia` | Texto exacto que recibe el modelo (auditoría) |

Documentación interactiva en `/docs`.

---

## Contexto académico

Desarrollado para la asignatura **Análisis y Gerencia Financiera** de la
Universidad El Bosque, a partir de:

- Baena Toro, D. (2014). *Análisis financiero: enfoque y proyecciones* (2ª ed.). Ecoe.
- García S., O. L. *Administración financiera: fundamentos y aplicaciones*.
- Barbosa Guerrero, L. M. (2021). *Análisis y gerencia financiera*. U. El Bosque.

[FORMULAS.md](FORMULAS.md) documenta las discrepancias encontradas entre el
material del curso y los criterios adoptados por esta aplicación, con la
justificación de cada una.

---

## Licencia

MIT — ver [LICENSE](LICENSE).

## Aviso

Herramienta educativa. No constituye asesoría financiera, contable ni
tributaria. Las decisiones sobre una empresa real deben tomarse con el
acompañamiento de un profesional.
