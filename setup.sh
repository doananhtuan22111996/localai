#!/bin/bash
# setup.sh — Quick LocalAI setup
set -e

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "   🤖 LocalAI Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── 1. Check Python ───────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "❌ Python 3 is not installed. Download at: https://python.org"
    exit 1
fi
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "✓ Python $PYTHON_VERSION"

# ── 2. Create virtual environment ───────────────────────────────
if [ ! -d ".venv" ]; then
    echo "→ Creating virtual environment..."
    python3 -m venv .venv
fi
echo "✓ Virtual environment"

# ── 3. Activate venv ─────────────────────────────────────────────
source .venv/bin/activate

# ── 4. Install dependencies ──────────────────────────────────────
echo "→ Installing packages..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "✓ Packages installed"

# ── 5. Create launcher script ────────────────────────────────────
cat > localai << 'EOF'
#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/.venv/bin/activate"
python "$DIR/main.py" "$@"
EOF
chmod +x localai
echo "✓ Launcher script created"

# ── 6. Check Ollama ──────────────────────────────────────────────
echo ""
echo "━━━ Check Ollama ━━━━━━━━━━━━━━━━━━━━━━━━"
if command -v ollama &>/dev/null; then
    echo "✓ Ollama installed"
    # Check models
    for model in "qwen2.5:7b" "llama3.2"; do
        model_base="${model%%:*}"
        if ollama list 2>/dev/null | grep -q "$model_base"; then
            echo "✓ Model $model available"
        else
            echo "→ Pulling model $model (first time may take a few minutes)..."
            ollama pull "$model"
            echo "✓ Model $model ready"
        fi
    done
else
    echo ""
    echo "⚠  Ollama is not installed."
    echo "   Download at: https://ollama.com"
    echo "   After installing, run: ollama pull qwen2.5:7b"
    echo ""
    echo "   Or use Groq (free, no GPU needed):"
    echo "   1. Sign up at: https://console.groq.com"
    echo "   2. Get an API key"
    echo "   3. Run: ./localai --base-url https://api.groq.com/openai/v1 \\"
    echo "                     --api-key gsk_xxx \\"
    echo "                     --model llama-3.3-70b-versatile"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Setup complete!"
echo ""
echo "How to run:"
echo "  ./localai                    # Start chatting"
echo "  ./localai --model llama3.2   # Use a different model"
echo "  ./localai --help             # View all options"
echo ""
