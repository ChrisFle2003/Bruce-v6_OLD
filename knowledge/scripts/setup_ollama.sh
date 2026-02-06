#!/bin/bash
set -e

echo "=================================================="
echo "Bruce Hierarchical Knowledge - Ollama Setup"
echo "=================================================="

OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
EMBEDDING_MODEL="${EMBEDDING_MODEL:-nomic-embed-text}"

echo ""
echo "1. Checking Ollama connection..."
echo "   Host: $OLLAMA_HOST"

# Try to connect to Ollama
if ! curl -s "${OLLAMA_HOST}/api/tags" > /dev/null 2>&1; then
    echo "   [ERROR] Ollama not responding at $OLLAMA_HOST"
    echo ""
    echo "   To run Ollama locally:"
    echo "   1. Install from: https://ollama.com"
    echo "   2. Run: ollama serve"
    echo "   3. In another terminal, continue this script"
    exit 1
fi

echo "   [OK] Ollama is running"

echo ""
echo "2. Checking embedding model..."
echo "   Model: $EMBEDDING_MODEL"

# List available models
MODELS=$(curl -s "${OLLAMA_HOST}/api/tags" | grep -o '"name":"[^"]*"' | cut -d'"' -f4 | tr '\n' ' ' || echo "")

if echo "$MODELS" | grep -q "$EMBEDDING_MODEL"; then
    echo "   [OK] Model '$EMBEDDING_MODEL' already available"
else
    echo "   [INFO] Model not found. Available models: $MODELS"
    echo ""
    echo "   Pulling $EMBEDDING_MODEL (this may take a few minutes)..."

    curl -X POST "$OLLAMA_HOST/api/pull" \
        -H "Content-Type: application/json" \
        -d "{\"name\":\"$EMBEDDING_MODEL\"}" \
        --progress-bar

    echo ""
    echo "   [OK] Model pulled successfully"
fi

echo ""
echo "3. Testing embeddings..."

# Test embedding
RESPONSE=$(curl -s -X POST "$OLLAMA_HOST/api/embeddings" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"$EMBEDDING_MODEL\",\"prompt\":\"test\"}")

if echo "$RESPONSE" | grep -q "embedding"; then
    echo "   [OK] Embeddings working"

    # Count dimensions
    DIMS=$(echo "$RESPONSE" | grep -o '\[.*\]' | wc -w)
    echo "   Embedding dimensions: ~$DIMS"
else
    echo "   [ERROR] Embedding test failed"
    echo "   Response: $RESPONSE"
    exit 1
fi

echo ""
echo "=================================================="
echo "Ollama setup complete!"
echo "=================================================="
echo ""
echo "Next steps:"
echo "1. Start Python embedder: python knowledge/services/hierarchical_embedder.py"
echo "2. Run search service: python knowledge/services/hierarchical_search_mvp.py"
