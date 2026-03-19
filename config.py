"""
config.py — Configuration management for LocalAI
Supports: YAML config file + env variable override
"""
from __future__ import annotations

import os
import yaml
import dataclasses
from pathlib import Path
from dataclasses import dataclass

CONFIG_PATH = Path.home() / ".config" / "localai" / "config.yaml"

# ── Model Presets ─────────────────────────────────────────────
MODEL_PRESETS = [
    {
        "name": "Ollama — qwen2.5:7b (local)",
        "model": "qwen2.5:7b",
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
    },
    {
        "name": "Ollama — qwen2.5-coder:7b (local)",
        "model": "qwen2.5-coder:7b",
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
    },
    {
        "name": "Ollama — llama3.2 (local)",
        "model": "llama3.2",
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
    },
    {
        "name": "Groq — llama-3.3-70b-versatile (cloud)",
        "model": "llama-3.3-70b-versatile",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": os.environ.get("GROQ_API_KEY", ""),
    },
]


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

    # ── Search Settings ───────────────────────────────────────────
    search_provider: str = "auto"       # auto | tavily | duckduckgo
    tavily_api_key: str = ""            # Tavily API key (from YAML, env var TAVILY_API_KEY, or both)

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
            "LOCALAI_MODEL":       ("model",      str),
            "LOCALAI_BASE_URL":    ("base_url",   str),
            "LOCALAI_API_KEY":     ("api_key",    str),
            "LOCALAI_MAX_TOKENS":  ("max_tokens", int),
            "LOCALAI_STREAM":      ("stream",     lambda v: v.lower() in ("1", "true", "yes")),
            "LOCALAI_SEARCH_PROVIDER": ("search_provider", str),
            "TAVILY_API_KEY":      ("tavily_api_key", str),
        }
        for env_key, (field_name, coerce) in env_map.items():
            if val := os.environ.get(env_key):
                data[field_name] = coerce(val)

        valid = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in data.items() if k in valid})

    def apply_preset(self, preset: dict):
        """Apply a model preset to this config."""
        self.model = preset["model"]
        self.base_url = preset["base_url"]
        self.api_key = preset["api_key"]

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
