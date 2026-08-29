# ---------------------------------------------------------------------------
# Palpito - imagen de produccion
#
# Un solo contenedor: FastAPI calcula los indicadores Y sirve la interfaz.
# Sin build de frontend, sin Node, sin proxy interno.
# ---------------------------------------------------------------------------
FROM python:3.12-slim

# Buenas practicas de Python en contenedor
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Las dependencias primero: si no cambian, Docker reutiliza esta capa
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Codigo de la aplicacion
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY casos/ ./casos/

# No correr como root
RUN useradd --create-home --uid 1000 palpito && chown -R palpito:palpito /app
USER palpito

EXPOSE 8000

# Dokploy y Traefik consultan este endpoint para saber si el servicio vive
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/salud', timeout=4).status==200 else 1)"

WORKDIR /app/backend
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
