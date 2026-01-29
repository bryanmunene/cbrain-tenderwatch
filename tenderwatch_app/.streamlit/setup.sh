#!/bin/bash
# Streamlit Cloud setup script - automatically runs on deployment

echo "📦 Downloading spaCy en_core_web_sm model..."
python -m spacy download en_core_web_sm --no-deps 2>&1 || {
    echo "⚠️  spaCy model download failed, continuing with regex fallback"
    exit 0
}
echo "✅ spaCy model installed successfully"
