#!/bin/bash

# 停止本地开发服务（dev.sh 启动的 uvicorn，默认 8000 端口）

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${DEV_PORT:-8000}"

echo "🛑 Stopping dev service on port ${PORT}..."

pids=$(lsof -t -i:"${PORT}" 2>/dev/null || true)

if [ -z "$pids" ]; then
  echo "ℹ️  No process found on port ${PORT}"
  exit 0
fi

echo "Found PID(s): $pids"

# 先尝试优雅退出
kill $pids 2>/dev/null || true
sleep 2

remaining=$(lsof -t -i:"${PORT}" 2>/dev/null || true)
if [ -n "$remaining" ]; then
  echo "⚠️  Process still running, force killing..."
  kill -9 $remaining 2>/dev/null || true
  sleep 1
fi

still=$(lsof -t -i:"${PORT}" 2>/dev/null || true)
if [ -n "$still" ]; then
  echo "❌ Failed to stop process on port ${PORT} (PID: $still)"
  exit 1
fi

echo "✅ Dev service stopped (port ${PORT} is free)"
