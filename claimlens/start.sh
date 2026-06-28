#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$SCRIPT_DIR/backend"
FRONTEND="$SCRIPT_DIR/frontend"

echo ""
echo "  ██████╗██╗      █████╗ ██╗███╗   ███╗██╗     ███████╗███╗   ██╗███████╗"
echo "  ██╔════╝██║     ██╔══██╗██║████╗ ████║██║     ██╔════╝████╗  ██║██╔════╝"
echo "  ██║     ██║     ███████║██║██╔████╔██║██║     █████╗  ██╔██╗ ██║███████╗"
echo "  ██║     ██║     ██╔══██║██║██║╚██╔╝██║██║     ██╔══╝  ██║╚██╗██║╚════██║"
echo "  ╚██████╗███████╗██║  ██║██║██║ ╚═╝ ██║███████╗███████╗██║ ╚████║███████║"
echo "   ╚═════╝╚══════╝╚═╝  ╚═╝╚═╝╚═╝     ╚═╝╚══════╝╚══════╝╚═╝  ╚═══╝╚══════╝"
echo ""
echo "  ClaimLens AI — Evidence-backed Medicare Part B wound care billing triage"
echo ""

# Check for ANTHROPIC_API_KEY
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "  ⚠️  ANTHROPIC_API_KEY not set — LLM extraction will be skipped."
    echo "     Export it with: export ANTHROPIC_API_KEY=sk-ant-..."
    echo ""
fi

# Kill any existing instances
pkill -f "uvicorn main:app" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
sleep 1

echo "  Starting backend (FastAPI) on port 8000..."
cd "$BACKEND"
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload > /tmp/claimlens-backend.log 2>&1 &
BACKEND_PID=$!

echo "  Starting frontend (Vite) on port 5173..."
cd "$FRONTEND"
npm run dev > /tmp/claimlens-frontend.log 2>&1 &
FRONTEND_PID=$!

# Wait for backend
echo ""
echo "  Waiting for services..."
for i in {1..15}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        break
    fi
    sleep 1
done

echo ""
echo "  ✅ ClaimLens AI is running!"
echo ""
echo "  🌐 Dashboard:  http://localhost:5173"
echo "  🔧 API:        http://localhost:8000"
echo "  📋 API docs:   http://localhost:8000/docs"
echo ""
echo "  → Click 'Sync Data' in the UI to pull 300 patients from the PCC API."
echo "  → Set use_llm=true in the sync call for Claude-powered extraction."
echo ""
echo "  Logs: /tmp/claimlens-backend.log  /tmp/claimlens-frontend.log"
echo ""
echo "  Press Ctrl+C to stop."
echo ""

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo '  Stopped.'; exit 0" INT TERM
wait
