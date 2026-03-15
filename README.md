# LocalAI — Terminal AI Assistant

> Claude Code / Cursor for your local machine, free, works with any model.

---

## Features

- **Read & understand codebase** — Automatically reads project structure, README, package.json on startup
- **Run bash commands** — AI runs `npm install`, `pytest`, `git commit`... when needed
- **Web search** — DuckDuckGo search with no API key required for research and debugging
- **Read/write files** — Create new files, edit code, refactor on demand
- **Slash commands** — `/add`, `/model`, `/cd`, `/clear`... similar to Aider
- **Multi-provider** — Ollama (local), Groq (free cloud), OpenRouter, any OpenAI-compatible API

---

## Quick Setup

```bash
git clone <repo> localai
cd localai
bash setup.sh
```

The script will automatically:
1. Create a virtual environment
2. Install all dependencies
3. Create the `./localai` launcher
4. Pull the `qwen2.5:7b` model if Ollama is installed

---

## Usage

```bash
# Use Ollama (default, requires Ollama to be installed)
./localai

# Choose a lighter model
./localai --model qwen2.5:3b
./localai --model llama3.2:3b
./localai --model phi4-mini

# Use Groq (free, no GPU needed — sign up at console.groq.com)
./localai \
  --base-url https://api.groq.com/openai/v1 \
  --api-key gsk_xxxx \
  --model llama-3.3-70b-versatile

# One-shot (non-interactive)
./localai --prompt "Explain what main.py does"

# View current config
./localai --config
```

---

## Slash Commands

| Command | Description |
|---------|-------------|
| `/help` | Show this menu |
| `/clear` | Clear conversation history |
| `/model <name>` | Switch the active model |
| `/add <file>` | Add a file to context (AI will read it carefully) |
| `/files` | View files currently in context |
| `/cd <path>` | Change working directory |
| `/config` | View current configuration |
| `/tokens` | Estimate current token usage |
| `/save` | Save config to file |
| `/exit` | Quit |

---

## Configuration

Create a file at `~/.config/localai/config.yaml`:

```yaml
# Default model
model: qwen2.5:7b
base_url: http://localhost:11434/v1
api_key: ollama

# Or use Groq
# model: llama-3.3-70b-versatile
# base_url: https://api.groq.com/openai/v1
# api_key: gsk_xxxx

# Settings
max_tokens: 8192
temperature: 0.1          # Lower = more consistent for coding
max_iterations: 30        # Max tool-calling loops
show_tool_calls: true     # Show which tools AI is calling
```

Or use environment variables:
```bash
export LOCALAI_MODEL=llama3.2
export LOCALAI_BASE_URL=http://localhost:11434/v1
export LOCALAI_API_KEY=ollama
```

---

## Recommended Models

### Local (Ollama)

| Model | RAM Required | Quality | Notes |
|-------|-------------|---------|-------|
| `qwen2.5:7b` | 6GB | ⭐⭐⭐⭐ | Recommended, multilingual support |
| `qwen2.5-coder:7b` | 6GB | ⭐⭐⭐⭐⭐ | Best for coding |
| `llama3.2:3b` | 3GB | ⭐⭐⭐ | Lightweight, for low-end machines |
| `phi4-mini` | 3GB | ⭐⭐⭐⭐ | Microsoft, small but powerful |
| `deepseek-r1:7b` | 6GB | ⭐⭐⭐⭐ | Great for reasoning/logic |

```bash
# Install a model
ollama pull qwen2.5:7b
ollama pull qwen2.5-coder:7b
```

### Free Cloud (no GPU needed)

| Provider | URL | How to get a key |
|----------|-----|-----------------|
| **Groq** | `https://api.groq.com/openai/v1` | console.groq.com |
| **Google AI Studio** | `https://generativelanguage.googleapis.com/v1beta/openai/` | aistudio.google.com |
| **OpenRouter** | `https://openrouter.ai/api/v1` | openrouter.ai (many free models) |

---

## Project Structure

```
localai/
├── main.py       # Entry point, REPL loop, slash commands
├── agent.py      # Core agent loop (tool-calling with LLM)
├── tools.py      # All tools: file, bash, search, web
├── context.py    # Build system prompt from codebase context
├── display.py    # Terminal UI with Rich
├── config.py     # Config management
├── requirements.txt
└── setup.sh
```

### How It Works

```
User input
    │
    ▼
[agent.py] Build messages (system prompt + history)
    │
    ▼
[LLM] Think → may call tools
    │
    ├─ tool_call? ──► [tools.py] Execute tool
    │                     │
    │                     └──► Result → back to LLM
    │
    └─ text response ──► [display.py] Render → User
```

---

## Adding Custom Tools

Add a new tool in `tools.py`:

```python
# 1. Write the function
def my_tool(param: str) -> str:
    return "result"

# 2. Add the schema
TOOL_SCHEMAS.append({
    "type": "function",
    "function": {
        "name": "my_tool",
        "description": "Description so the LLM knows when to use this tool",
        "parameters": {
            "type": "object",
            "properties": {
                "param": {"type": "string", "description": "..."},
            },
            "required": ["param"],
        },
    },
})

# 3. Register the handler
TOOL_HANDLERS["my_tool"] = my_tool
```

---

## Future Ideas

- **Memory** — Persist context across sessions with SQLite
- **RAG** — Index large codebases with embeddings (ChromaDB + nomic-embed)
- **Git integration** — Auto commit, create PRs, review diffs
- **Streaming** — Stream responses instead of waiting for the full output
- **MCP support** — Connect to MCP servers (Jira, Slack, Notion...)
- **Vision** — Recognize screenshots/images with multimodal models
