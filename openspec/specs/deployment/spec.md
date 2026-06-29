# deployment Specification

## Purpose
Define containerized deployment requirements for the Yunshu API Data Platform.
定义云枢数据服务平台的容器化部署要求。

## Requirements

### Requirement: Containerization
The system MUST support containerized deployment via Docker.
系统必须支持通过 Docker 进行容器化部署。

#### Scenario: Docker Build
- WHEN running `docker build -f docker/Dockerfile`
- THEN a runnable Docker image containing the API service MUST be created successfully.
- AND the image MUST use multi-stage build (frontend + Python runtime).
- AND the image SHOULD include a HEALTHCHECK on `/health`.

#### Scenario: Production Process Model
- WHEN running the production Docker image
- THEN the API MUST be served via gunicorn with uvicorn workers.
- AND `WEB_CONCURRENCY` MUST be configurable via environment variable.

### Requirement: Service Orchestration
The system MUST provide orchestration configurations for both development and production scenarios.
系统必须提供面向开发和生产场景的编排配置。

#### Scenario: Development Stack
- WHEN running `docker compose -f docker/docker-compose.dev.yml up`
- THEN API and Redis services MUST start.
- AND the API container MAY mount source code for hot reload.

#### Scenario: Production Stack
- WHEN running `docker compose -f docker/docker-compose.yml up`
- THEN API and Redis services MUST start without source code bind-mount.

#### Scenario: Standalone API Mode
- WHEN running `docker compose -f docker/docker-compose.api.yml up`
- THEN only the API service MUST start.
- AND it MUST connect to external MySQL and Redis via environment variables.

### Requirement: Background Jobs
The system MUST run scheduled jobs (log aggregation, log cleanup) without duplicate execution in multi-worker deployments.
系统必须在多 Worker 部署下避免定时任务重复执行。

#### Scenario: Scheduler Deduplication
- WHEN multiple gunicorn workers are running with `ENABLE_SCHEDULER=1`
- THEN each scheduled job MUST execute at most once per interval (via Redis distributed lock).

### Requirement: Build Automation
The system MUST provide scripts to automate image building and exporting.
系统必须提供脚本以自动化镜像构建和导出。

#### Scenario: Build Script
- WHEN executing `docker/build_linux_x86.sh <version>` or `docker/build_native.sh <version>`
- THEN the script MUST build a versioned image for the target platform.
- AND export it to `docker/release/` directory.
