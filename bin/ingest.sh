#!/bin/bash
set -e

# Activate virtual environment
cd "$(dirname "$0")/.."
source venv/bin/activate

# Load environment
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Run ingest
echo "📥 Ingesting sources..."
python -m backend.pipeline.cli ingest --all

# Generate digest
echo "📊 Generating digest..."
python -m backend.pipeline.cli digest

echo "✅ Ingest complete"
