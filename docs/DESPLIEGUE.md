# Despliegue de Pálpito

Guía específica para el servidor donde vive el proyecto. Escrita a partir de la
infraestructura real, no de un tutorial genérico.

## Infraestructura

| | |
|---|---|
| Servidor | Contabo VPS — Ubuntu 24.04 |
| Panel | Dokploy → `https://dokploy.vitalii.com.co` |
| Proxy inverso | Traefik (gestionado por Dokploy), red `dokploy-network` |
| Certificados | Let's Encrypt, automáticos |
| Firewall | Contabo — solo 22 / 80 / 443 abiertos |
| Dominio de la app | `finanzas.torbex.com.co` |
| DNS | Namecheap → registro `A` · `finanzas` → IP del VPS |

---

## Paso 1 — Publicar el repositorio en GitHub

```bash
cd palpito
git add .
git commit -m "Pálpito: motor, API, interfaz y narrativa IA"
git branch -M main
git remote add origin https://github.com/USUARIO/palpito.git
git push -u origin main
```

> **Antes de hacer push, verifica que `.env` NO esté incluido:**
> ```bash
> git status --short | grep -i env    # solo debe aparecer .env.example
> git check-ignore -v .env            # debe responder ".gitignore:1:.env"
> ```
> Si `.env` llegara a subirse, la clave de OpenRouter queda pública y hay que
> revocarla de inmediato en <https://openrouter.ai/keys>. Borrarla del repo
> después **no** es suficiente: queda en el historial de git.

---

## Paso 2 — Crear el servicio en Dokploy

Entrar a `https://dokploy.vitalii.com.co` y dentro del proyecto:

1. **Create Service → Application**

   > ⚠️ **Application, no Compose.** Es la lección aprendida del incidente
   > documentado en la guía maestra de infraestructura: los servicios creados vía
   > Template/Compose quedan en su propia red Docker y hay que reconectarlos a
   > `dokploy-network` con `docker network connect` **después de cada
   > redespliegue**. Los servicios tipo Application se unen solos.

2. **Provider:** GitHub (o Git con la URL del repositorio)
   **Branch:** `main`

3. **Build Type:** `Dockerfile`
   **Docker File Path:** `Dockerfile`

4. **Environment** — pegar las variables:
   ```
   OPENROUTER_API_KEY=sk-or-v1-...
   OPENROUTER_MODELO=deepseek/deepseek-v4-flash
   ```
   Aquí es donde vive la clave: en el servidor, nunca en el repositorio ni en el
   navegador del usuario.

5. **Domains → Add Domain**
   | Campo | Valor |
   |---|---|
   | Host | `finanzas.torbex.com.co` |
   | Path | `/` |
   | Container Port | `8000` |
   | HTTPS | activado |
   | Certificate Provider | Let's Encrypt |

6. **Deploy**

---

## Paso 3 — Verificar

```bash
# Certificado válido y emitido por Let's Encrypt
curl -vI https://finanzas.torbex.com.co 2>&1 | grep -i "issuer\|HTTP/"

# La API responde y reporta si la IA está configurada
curl -s https://finanzas.torbex.com.co/api/salud
```

Respuesta esperada:

```json
{"estado":"ok","version":"0.3.0","ia":{"disponible":true,"modelo":"deepseek/deepseek-v4-flash","motivo":""}}
```

Si `ia.disponible` sale en `false`, la variable de entorno no llegó al
contenedor: revisar la sección *Environment* en Dokploy y redesplegar.

---

## Actualizaciones posteriores

```bash
git add . && git commit -m "descripción del cambio" && git push
```

Y en Dokploy: **Deploy**. (O activar *Auto Deploy* con el webhook de GitHub para
que se despliegue solo en cada push.)

---

## Problemas frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `Gateway Timeout` | El contenedor no está en `dokploy-network` | Verificar que el servicio sea tipo *Application*. Diagnóstico: `docker inspect NOMBRE \| grep -A3 Networks` |
| Certificado autofirmado | El DNS aún no propaga, o falta el Certificate Provider | Confirmar `dig finanzas.torbex.com.co` y revisar el ajuste en Dokploy |
| `ia.disponible: false` | Falta `OPENROUTER_API_KEY` en el entorno | Agregarla en *Environment* y redesplegar |
| Error 502 al redactar | Clave inválida o sin saldo en OpenRouter | Revisar <https://openrouter.ai/credits> |
| El panel de Dokploy no carga | El puerto 3000 está cerrado por el firewall | Entrar por `https://dokploy.vitalii.com.co`, no por IP:3000 |

---

## Prueba local antes de desplegar

Con Docker instalado:

```bash
docker compose up --build      # → http://localhost:8000
```

Sin Docker, directo con Python:

```bash
cd backend
pip install -r requirements.txt
python -m pytest -q             # deben pasar todas las pruebas
uvicorn api:app --reload        # → http://localhost:8000
```
