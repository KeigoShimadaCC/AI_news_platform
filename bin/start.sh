#!/bin/bash
set -e

echo "🚀 Starting AI News Platform..."

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "❌ Virtual environment not found. Run ./bin/setup.sh first"
    exit 1
fi

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env not found, using defaults"
fi

# Ensure database exists and is migrated
DB_FILE="data/ainews.db"
if [ ! -f "$DB_FILE" ]; then
    echo "📥 First run - initializing database..."
    python -m backend.storage.migrations upgrade
    echo "   To fetch content: python -m backend.pipeline.cli ingest --all && python -m backend.pipeline.cli digest"
fi

# Start Next.js in background
echo "🌐 Starting web UI on http://localhost:3000"
npm run dev > /tmp/ainews-ui.log 2>&1 &
UI_PID=$!

# Trap to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down..."
    kill $UI_PID 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

echo ""
echo "✅ AI News Platform is running!"
echo ""
echo "  Web UI: http://localhost:3000"
echo "  Logs:   tail -f /tmp/ainews-ui.log"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Wait for UI process
wait $UI_PID
