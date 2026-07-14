FROM python:3.12-slim

ARG TARGETARCH
ARG COMPOSE_VERSION=2.27.1

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl docker-cli git iputils-ping rsync \
    && case "$TARGETARCH" in arm64) compose_arch=aarch64 ;; amd64) compose_arch=x86_64 ;; *) echo "unsupported architecture: $TARGETARCH" >&2; exit 1 ;; esac \
    && mkdir -p /usr/local/lib/docker/cli-plugins \
    && curl -fsSL "https://github.com/docker/compose/releases/download/v${COMPOSE_VERSION}/docker-compose-linux-${compose_arch}" -o /usr/local/lib/docker/cli-plugins/docker-compose \
    && chmod +x /usr/local/lib/docker/cli-plugins/docker-compose \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install .

RUN mkdir -p /app/.paledit-data /app/Save
EXPOSE 18765
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:18765/api/health', timeout=3)"

CMD ["palops", "serve", "--host", "0.0.0.0", "--port", "18765"]
