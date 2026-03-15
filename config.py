"""
config.py — Configuration management for LocalAI
Supports: YAML config file + env variable override
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
    model: str = "qwen2.5:7b"           # Ollama model to use
    base_url: str = "http://localhost:11434/v1"  # Ollama local API
    api_key: str = "ollama"             # Ollama doesn't need a real key

    # To use Groq (free API, faster):
    #   base_url = "https://api.groq.com/openai/v1"
    #   api_key  = "gsk_xxxx"   (get at console.groq.com)
    #   model    = "llama-3.3-70b-versatile"

    # ── Generation Settings ────────────────────────────────────────
    max_tokens: int = 8192
    temperature: float = 0.1            # Low → more consistent for coding
    max_iterations: int = 30            # Max tool-calling loops

    # ── Context Settings ───────────────────────────────────────────
    max_file_size_kb: int = 150         # Skip files larger than this
    max_context_files: int = 20         # Max files to include in context
    auto_context: bool = True           # Auto-read directory structure

    # ── UI Settings ────────────────────────────────────────────────
    show_tool_calls: bool = True        # Show which tool is being called
    stream: bool = True                 # Stream output instead of waiting

    @classmethod
    def load(cls) -> "Config":
        """Load config from YAML file, then override with env vars if present."""
        data = {}

        if CONFIG_PATH.exists():
            with open(CONFIG_PATH) as f:
                data = yaml.safe_load(f) or {}

        # Env var overrides — convenient when switching between projects
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
        """Save current config to file."""
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            yaml.dump(dataclasses.asdict(self), f, default_flow_style=False)

    def show(self):
        """Display current config (mask api_key)."""
        d = dataclasses.asdict(self)
        if d.get("api_key") and d["api_key"] not in ("ollama", ""):
            d["api_key"] = d["api_key"][:8] + "..."
        return d
