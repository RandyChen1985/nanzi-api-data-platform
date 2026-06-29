#!/bin/bash
# 等待服务就绪脚本

set -e

echo "🔍 Checking service dependencies..."

if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

MYSQL_HOST="${MYSQL_HOST:-localhost}"
MYSQL_PORT="${MYSQL_PORT:-3306}"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
timeout=60

echo "⏳ Waiting for MySQL at ${MYSQL_HOST}:${MYSQL_PORT}..."
counter=0
until nc -z "${MYSQL_HOST}" "${MYSQL_PORT}" 2>/dev/null; do
    counter=$((counter + 1))
    if [ "$counter" -gt "$timeout" ]; then
        echo "❌ MySQL is not available after ${timeout}s"
        exit 1
    fi
    sleep 1
done
echo "✅ MySQL is ready"

if [ "${REDIS_ENABLE}" = "true" ] || [ "${REDIS_ENABLE}" = "True" ] || [ "${REDIS_ENABLE}" = "1" ]; then
    echo "⏳ Waiting for Redis at ${REDIS_HOST}:${REDIS_PORT}..."
    counter=0
    until nc -z "${REDIS_HOST}" "${REDIS_PORT}" 2>/dev/null; do
        counter=$((counter + 1))
        if [ "$counter" -gt "$timeout" ]; then
            echo "❌ Redis is not available after ${timeout}s"
            exit 1
        fi
        sleep 1
    done
    echo "✅ Redis is ready"
else
    echo "⚠️  Redis check skipped (REDIS_ENABLE=false)"
fi

echo ""
echo "🚀 Dependencies ready. Starting application..."
echo ""
