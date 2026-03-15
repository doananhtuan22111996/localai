"""
config.py — Quản lý cấu hình cho LocalAI
Hỗ trợ: config file YAML + env variable override
"""
import os
import yaml
import dataclasses
from pathlib import Path
from dataclasses import dataclass, field

CONFIG_PATH = Path.home() / ".config" / "localai" / "config.yaml"


@dataclass
class Config:
    # ── LLM Settings ──────────────────────────────────────────────
    model: str = "qwen2.5:7b"           # Model Ollama muốn dùng
    base_url: str = "http://localhost:11434/v1"  # Ollama local API
    api_key: str = "ollama"             # Ollama không cần key thật

    # Nếu dùng Groq (free API, nhanh hơn):
    #   base_url = "https://api.groq.com/openai/v1"
    #   api_key  = "gsk_xxxx"   (lấy tại console.groq.com)
    #   model    = "llama-3.3-70b-versatile"

    # ── Generation Settings ────────────────────────────────────────
    max_tokens: int = 8192
    temperature: float = 0.1            # Thấp → consistent hơn khi code
    max_iterations: int = 30            # Số vòng tool-calling tối đa

    # ── Context Settings ───────────────────────────────────────────
    max_file_size_kb: int = 150         # Bỏ qua file lớn hơn mức này
    max_context_files: int = 20         # Số file tối đa đưa vào context
    auto_context: bool = True           # Tự động đọc cấu trúc thư mục

    # ── UI Settings ────────────────────────────────────────────────
    show_tool_calls: bool = True        # Hiện tool nào đang được gọi
    stream: bool = True                 # Stream output thay vì chờ full

    @classmethod
    def load(cls) -> "Config":
        """Load config từ file YAML, sau đó override bằng env vars nếu có."""
        data = {}

        if CONFIG_PATH.exists():
            with open(CONFIG_PATH) as f:
                data = yaml.safe_load(f) or {}

        # Env var overrides — tiện khi dùng nhiều project khác nhau
        env_map = {
            "LOCALAI_MODEL":       "model",
            "LOCALAI_BASE_URL":    "base_url",
            "LOCALAI_API_KEY":     "api_key",
            "LOCALAI_MAX_TOKENS":  "max_tokens",
            "LOCALAI_STREAM":      "stream",
        }
        for env_key, field_name in env_map.items():
            if val := os.environ.get(env_key):
                data[field_name] = val

        valid = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in data.items() if k in valid})

    def save(self):
        """Lưu config hiện tại ra file."""
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            yaml.dump(dataclasses.asdict(self), f, default_flow_style=False)

    def show(self):
        """In ra config hiện tại (ẩn api_key)."""
        d = dataclasses.asdict(self)
        if d.get("api_key") and d["api_key"] not in ("ollama", ""):
            d["api_key"] = d["api_key"][:8] + "..."
        return d
