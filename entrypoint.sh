#!/bin/bash
set -e

echo "Starting Ollama service..."
ollama serve &

echo "Waiting for Ollama..."
until curl -s http://127.0.0.1:11434/ > /dev/null; do
    sleep 1
done

echo "Building KAI-1 model..."
ollama create kai-1 -f /app/Modelfile

echo "Starting FastAPI server..."
exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
