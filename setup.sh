#!/bin/bash
# setup.sh — Cài đặt LocalAI nhanh
set -e

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "   🤖 LocalAI Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── 1. Kiểm tra Python ──────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "❌ Python 3 chưa được cài. Tải tại: https://python.org"
    exit 1
fi
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "✓ Python $PYTHON_VERSION"

# ── 2. Tạo virtual environment ──────────────────────────────────
if [ ! -d ".venv" ]; then
    echo "→ Tạo virtual environment..."
    python3 -m venv .venv
fi
echo "✓ Virtual environment"

# ── 3. Activate venv ────────────────────────────────────────────
source .venv/bin/activate

# ── 4. Cài dependencies ─────────────────────────────────────────
echo "→ Cài packages..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "✓ Packages đã cài xong"

# ── 5. Tạo launcher script ──────────────────────────────────────
cat > localai << 'EOF'
#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/.venv/bin/activate"
python "$DIR/main.py" "$@"
EOF
chmod +x localai
echo "✓ Launcher script tạo xong"

# ── 6. Kiểm tra Ollama ──────────────────────────────────────────
echo ""
echo "━━━ Kiểm tra Ollama ━━━━━━━━━━━━━━━━━━━━━"
if command -v ollama &>/dev/null; then
    echo "✓ Ollama đã cài"
    # Kiểm tra model
    if ollama list 2>/dev/null | grep -q "qwen2.5"; then
        echo "✓ Model qwen2.5 có sẵn"
    else
        echo "→ Pulling model qwen2.5:7b (lần đầu có thể mất vài phút)..."
        ollama pull qwen2.5:7b
        echo "✓ Model đã sẵn sàng"
    fi
else
    echo ""
    echo "⚠  Ollama chưa cài."
    echo "   Tải tại: https://ollama.com"
    echo "   Sau khi cài xong, chạy: ollama pull qwen2.5:7b"
    echo ""
    echo "   Hoặc dùng Groq (miễn phí, không cần GPU):"
    echo "   1. Đăng ký tại: https://console.groq.com"
    echo "   2. Lấy API key"
    echo "   3. Chạy: ./localai --base-url https://api.groq.com/openai/v1 \\"
    echo "                      --api-key gsk_xxx \\"
    echo "                      --model llama-3.3-70b-versatile"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Setup hoàn tất!"
echo ""
echo "Cách chạy:"
echo "  ./localai                    # Bắt đầu chat"
echo "  ./localai --model llama3.2   # Dùng model khác"
echo "  ./localai --help             # Xem tất cả options"
echo ""
