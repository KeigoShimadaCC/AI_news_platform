#!/usr/bin/env bash
set -e

# Project root (parent of bin/)
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export OLLAMA_MODELS="${ROOT}/models"

mkdir -p "$OLLAMA_MODELS"

echo "OLLAMA_MODELS=$OLLAMA_MODELS"
echo "First time? In another terminal run: OLLAMA_MODELS=$OLLAMA_MODELS ollama pull smollm:1.7b"
echo ""
echo "If you see 'address already in use': Ollama is already running (e.g. from the app)."
echo "  - To use project models/: quit Ollama, then run this script again."
echo "  - To use the running server: just run 'ollama pull smollm:1.7b' (model will be in default dir)."
echo "Starting Ollama..."
exec ollama serve
