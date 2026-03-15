# 🤖 LocalAI — Terminal AI Assistant

> Claude Code / Cursor cho máy local, miễn phí, chạy với bất kỳ model nào.

---

## Tính năng

- **Đọc & hiểu codebase** — Tự động đọc cấu trúc project, README, package.json khi bắt đầu
- **Chạy bash commands** — AI tự chạy `npm install`, `pytest`, `git commit`... khi cần
- **Web search** — Tìm DuckDuckGo không cần API key để research, tra lỗi
- **Đọc/ghi file** — Tạo file mới, edit code, refactor theo yêu cầu
- **Slash commands** — `/add`, `/model`, `/cd`, `/clear`... giống Aider
- **Multi-provider** — Ollama (local), Groq (free cloud), OpenRouter, bất kỳ OpenAI-compatible API

---

## Cài đặt nhanh

```bash
git clone <repo> localai
cd localai
bash setup.sh
```

Script sẽ tự:
1. Tạo virtual environment
2. Cài tất cả dependencies
3. Tạo launcher `./localai`
4. Pull model `qwen2.5:7b` nếu Ollama đã cài

---

## Cách chạy

```bash
# Dùng Ollama (mặc định, cần cài Ollama trước)
./localai

# Chọn model nhẹ hơn
./localai --model qwen2.5:3b
./localai --model llama3.2:3b
./localai --model phi4-mini

# Dùng Groq (miễn phí, không cần GPU — đăng ký tại console.groq.com)
./localai \
  --base-url https://api.groq.com/openai/v1 \
  --api-key gsk_xxxx \
  --model llama-3.3-70b-versatile

# One-shot (không interactive)
./localai --prompt "Giải thích file main.py làm gì"

# Xem config hiện tại
./localai --config
```

---

## Slash Commands

| Command | Mô tả |
|---------|-------|
| `/help` | Hiện menu này |
| `/clear` | Xóa conversation history |
| `/model <tên>` | Đổi model đang dùng |
| `/add <file>` | Thêm file vào context (AI sẽ đọc kỹ file đó) |
| `/files` | Xem files đang trong context |
| `/cd <path>` | Đổi working directory |
| `/config` | Xem cấu hình hiện tại |
| `/tokens` | Ước tính tokens đang dùng |
| `/save` | Lưu config ra file |
| `/exit` | Thoát |

---

## Cấu hình

Tạo file `~/.config/localai/config.yaml`:

```yaml
# Model mặc định
model: qwen2.5:7b
base_url: http://localhost:11434/v1
api_key: ollama

# Hoặc dùng Groq
# model: llama-3.3-70b-versatile
# base_url: https://api.groq.com/openai/v1
# api_key: gsk_xxxx

# Cài đặt
max_tokens: 8192
temperature: 0.1          # Thấp = consistent hơn khi code
max_iterations: 30        # Số vòng tool-calling tối đa
show_tool_calls: true     # Hiện AI đang gọi tool gì
```

Hoặc dùng env vars:
```bash
export LOCALAI_MODEL=llama3.2
export LOCALAI_BASE_URL=http://localhost:11434/v1
export LOCALAI_API_KEY=ollama
```

---

## Model gợi ý

### Chạy local (Ollama)

| Model | RAM cần | Chất lượng | Ghi chú |
|-------|---------|------------|---------|
| `qwen2.5:7b` | 6GB | ⭐⭐⭐⭐ | Khuyên dùng, hỗ trợ tiếng Việt |
| `qwen2.5-coder:7b` | 6GB | ⭐⭐⭐⭐⭐ | Tốt nhất cho coding |
| `llama3.2:3b` | 3GB | ⭐⭐⭐ | Nhẹ, máy yếu |
| `phi4-mini` | 3GB | ⭐⭐⭐⭐ | Microsoft, nhỏ nhưng mạnh |
| `deepseek-r1:7b` | 6GB | ⭐⭐⭐⭐ | Tốt cho reasoning/logic |

```bash
# Cài model
ollama pull qwen2.5:7b
ollama pull qwen2.5-coder:7b
```

### Cloud miễn phí (không cần GPU)

| Provider | URL | Cách lấy key |
|----------|-----|--------------|
| **Groq** | `https://api.groq.com/openai/v1` | console.groq.com |
| **Google AI Studio** | `https://generativelanguage.googleapis.com/v1beta/openai/` | aistudio.google.com |
| **OpenRouter** | `https://openrouter.ai/api/v1` | openrouter.ai (nhiều model free) |

---

## Cấu trúc project

```
localai/
├── main.py       # Entry point, REPL loop, slash commands
├── agent.py      # Core agent loop (tool-calling với LLM)
├── tools.py      # Tất cả tools: file, bash, search, web
├── context.py    # Build system prompt từ codebase context
├── display.py    # Terminal UI với Rich
├── config.py     # Config management
├── requirements.txt
└── setup.sh
```

### Luồng hoạt động

```
User input
    │
    ▼
[agent.py] Build messages (system prompt + history)
    │
    ▼
[LLM] Suy nghĩ → có thể gọi tool
    │
    ├─ tool_call? ──► [tools.py] Execute tool
    │                     │
    │                     └──► Kết quả → back to LLM
    │
    └─ text response ──► [display.py] Render → User
```

---

## Mở rộng thêm tools

Thêm tool mới vào `tools.py`:

```python
# 1. Viết function
def my_tool(param: str) -> str:
    return "kết quả"

# 2. Thêm schema
TOOL_SCHEMAS.append({
    "type": "function",
    "function": {
        "name": "my_tool",
        "description": "Mô tả để LLM biết khi nào dùng tool này",
        "parameters": {
            "type": "object",
            "properties": {
                "param": {"type": "string", "description": "..."},
            },
            "required": ["param"],
        },
    },
})

# 3. Đăng ký handler
TOOL_HANDLERS["my_tool"] = my_tool
```

---

## Ý tưởng mở rộng tiếp theo

- **Memory** — Lưu context giữa các session bằng SQLite
- **RAG** — Index codebase lớn bằng embeddings (ChromaDB + nomic-embed)
- **Git integration** — Auto commit, tạo PR, review diff
- **Streaming** — Stream response thay vì chờ toàn bộ
- **MCP support** — Kết nối với MCP servers (Jira, Slack, Notion...)
- **Vision** — Nhận diện screenshot/hình ảnh với model multimodal
