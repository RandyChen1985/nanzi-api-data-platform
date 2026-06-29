#!/bin/bash

# 确保脚本在错误时停止
set -e

echo "🧹 Step 1: Cleaning..."
rm -rf frontend/dist app.log
echo "✅ Cleanup complete."

echo "🏗️  Step 2: Compiling Frontend..."
cd frontend
npm run build
cd ..
echo "✅ Frontend compilation complete."

echo "🛑 Step 3: Stopping old service..."
pid=$(lsof -t -i:8000 || true)
if [ -n "$pid" ]; then
  kill -9 $pid
  echo "✅ Killed process $pid"
else
  echo "ℹ️  No process found on port 8000"
fi

echo "🚀 Step 4: Starting new service..."
# 检查虚拟环境是否存在
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > app.log 2>&1 &
echo "✅ Service started in background (PID: $!)."

echo "⏳ Step 5: Waiting for service to start..."
sleep 5
echo "📜 Startup Logs:"
cat app.log
echo ""
echo "📡 Following logs (Ctrl+C to stop tail, service keeps running)..."
tail -f app.log
