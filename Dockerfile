# Clase en Vivo UNACHI — imagen para el MODO VPS (Dokploy / Docker)
FROM python:3.12-slim

ARG MEDIAMTX_VERSION=v1.21.1
# Docker BuildKit define TARGETARCH (amd64 | arm64) según la plataforma del VPS.
ARG TARGETARCH=amd64

ENV PYTHONUNBUFFERED=1 \
    CLASE_MODO=vps \
    CLASE_PUERTO_WEB=8080

WORKDIR /app

# MediaMTX (binario oficial, licencia MIT)
ADD https://github.com/bluenviron/mediamtx/releases/download/${MEDIAMTX_VERSION}/mediamtx_${MEDIAMTX_VERSION}_linux_${TARGETARCH}.tar.gz /tmp/mediamtx.tar.gz
RUN mkdir -p /app/mediamtx \
 && tar -xzf /tmp/mediamtx.tar.gz -C /app/mediamtx mediamtx LICENSE \
 && rm /tmp/mediamtx.tar.gz \
 && useradd --system --no-create-home --uid 10001 clase

COPY servidor_clase.py mediamtx.yml mediamtx.vps.yml ./
COPY web ./web

USER clase

# 8080/tcp: páginas + señalización WebRTC (detrás de Traefik, HTTPS)
# 8189/udp y 8189/tcp: medios WebRTC (publicados directamente en el host)
EXPOSE 8080 8189/udp 8189/tcp

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/salud', timeout=3).status == 200 else 1)"

CMD ["python", "servidor_clase.py", "--modo", "vps", "--sin-navegador"]
