#!/usr/bin/env bash
# Test local Ollama: check binary, check API is up, run one summarizer call.
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export OLLAMA_MODELS="${ROOT}/models"

if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama is not installed. Install from https://ollama.com then run this again."
  exit 1
fi

# Check if Ollama API is reachable (server must be running)
if ! curl -s -o /dev/null -w "%{http_code}" --connect-timeout 2 "http://localhost:11434/api/version" | grep -q 200; then
  echo "Ollama server is not running. Start it with: ./bin/start-ollama.sh"
  echo "Then (first time) in another terminal: OLLAMA_MODELS=$OLLAMA_MODELS ollama pull smollm:1.7b"
  exit 1
fi

# Run one summary via backend
source venv/bin/activate 2>/dev/null || true
python bin/test_ollama.py
