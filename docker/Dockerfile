# --- 阶段 1: 前端构建 ---
# PREBUILD_FRONTEND=1：宿主机已执行 vite build，仅 COPY dist（Mac 跨平台打 x86 包时推荐，避免容器 OOM）
ARG PREBUILD_FRONTEND=0
ARG APP_VERSION=dev
FROM node:20-slim AS frontend-builder
ARG PREBUILD_FRONTEND
ARG APP_VERSION
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN if [ "$PREBUILD_FRONTEND" != "1" ]; then npm ci || npm install; fi

COPY frontend/ .
RUN if [ "$PREBUILD_FRONTEND" = "1" ]; then \
      test -f dist/index.html || (echo "ERROR: PREBUILD_FRONTEND=1 但未找到 frontend/dist/index.html，请先在宿主机执行前端构建" && exit 1); \
      echo "使用宿主机预构建的前端产物"; \
    else \
      NODE_OPTIONS="--max-old-space-size=2048" VITE_APP_VERSION="$APP_VERSION" npx vite build; \
    fi

# --- 阶段 2: Python 环境构建 ---
FROM python:3.10-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV WEB_CONCURRENCY=4
ENV ENABLE_SCHEDULER=1
ENV DEBIAN_FRONTEND=noninteractive

# 系统依赖：Oracle(libaio)、健康检查(curl)、SQL Server(unixODBC + msodbcsql17/18)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    gnupg \
    && (apt-get install -y --no-install-recommends libaio1 \
        || apt-get install -y --no-install-recommends libaio1t64) \
    && ln -sf /usr/lib/x86_64-linux-gnu/libaio.so.1t64 /usr/lib/x86_64-linux-gnu/libaio.so.1 2>/dev/null || true \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
        | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && echo "deb [arch=amd64,arm64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" \
        > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && (ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql17 \
        || echo "WARN: msodbcsql17 unavailable, SQL Server legacy TLS fallback driver will not be installed") \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends \
        unixodbc \
        unixodbc-dev \
        msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install -r requirements.txt

COPY . .

COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

RUN useradd --create-home --shell /bin/bash appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["gunicorn", "app.main:app", "-c", "gunicorn.conf.py"]
