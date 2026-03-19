"""
tools.py — All tools the agent can call
Each tool has: schema (description for LLM) + handler (execution logic)
"""
from __future__ import annotations

import os
import json
import re
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import ipaddress


# ════════════════════════════════════════════════════════════════
# 1. FILE OPERATIONS
# ════════════════════════════════════════════════════════════════

def read_file(path: str) -> str:
    """Read the contents of a file."""
    try:
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = Path(os.getcwd()) / p
        if not p.exists():
            return f"[Error] File does not exist: {path}"
        size_kb = p.stat().st_size / 1024
        if size_kb > 500:
            return f"[Warning] File too large ({size_kb:.0f}KB). Read in parts instead."
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"[Error reading file] {e}"


def _is_path_safe(p: Path) -> bool:
    """Check that a resolved path is under the current working directory."""
    try:
        resolved = p.resolve()
        cwd = Path(os.getcwd()).resolve()
        resolved.relative_to(cwd)
        return True
    except ValueError:
        return False


def write_file(path: str, content: str) -> str:
    """Write content to a file (create new or overwrite). Restricted to cwd."""
    try:
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = Path(os.getcwd()) / p
        if not _is_path_safe(p):
            return f"[Blocked] Cannot write outside working directory: {path}"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"[OK] Wrote {p.stat().st_size} bytes to {path}"
    except Exception as e:
        return f"[Error writing file] {e}"


def list_directory(path: str = ".", recursive: bool = False) -> str:
    """List files in a directory. recursive=True to view the full tree."""
    try:
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = Path(os.getcwd()) / p
        if not p.is_dir():
            return f"[Error] Not a directory: {path}"

        # Directories/files to ignore
        IGNORE = {
            ".git", "__pycache__", "node_modules", ".venv", "venv",
            ".env", "dist", "build", ".next", ".cache", "*.pyc",
            ".DS_Store", "*.egg-info", ".pytest_cache", "coverage",
        }

        def should_ignore(name: str) -> bool:
            return any(
                name == ig or (ig.startswith("*") and name.endswith(ig[1:]))
                for ig in IGNORE
            )

        lines = [f"📁 {p.resolve()}/"]
        if recursive:
            for item in sorted(p.rglob("*")):
                if any(should_ignore(part) for part in item.parts):
                    continue
                depth = len(item.relative_to(p).parts)
                indent = "  " * (depth - 1)
                icon = "📄" if item.is_file() else "📁"
                lines.append(f"{indent}{icon} {item.name}")
        else:
            for item in sorted(p.iterdir()):
                if should_ignore(item.name):
                    continue
                icon = "📁" if item.is_dir() else "📄"
                lines.append(f"  {icon} {item.name}")

        return "\n".join(lines)
    except Exception as e:
        return f"[Error] {e}"


def search_in_files(query: str, path: str = ".", file_pattern: str = "*") -> str:
    """Search for text in files within a directory (internal grep)."""
    try:
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = Path(os.getcwd()) / p
        results = []
        count = 0
        for file in sorted(p.rglob(file_pattern)):
            if count > 200:
                results.append("... (stopped at 200 results)")
                break
            if not file.is_file():
                continue
            # Skip binary & ignored directories
            skip_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv"}
            if any(part in skip_dirs for part in file.parts):
                continue
            try:
                text = file.read_text(encoding="utf-8", errors="ignore")
                for i, line in enumerate(text.splitlines(), 1):
                    if query.lower() in line.lower():
                        rel = file.relative_to(p)
                        results.append(f"{rel}:{i}: {line.strip()}")
                        count += 1
            except Exception:
                continue
        if not results:
            return f"No results found for '{query}' in {path}"
        return "\n".join(results)
    except Exception as e:
        return f"[Error searching] {e}"


# ════════════════════════════════════════════════════════════════
# 2. BASH / SHELL EXECUTION
# ════════════════════════════════════════════════════════════════

# Patterns that indicate dangerous commands
BLOCKED_PATTERNS = [
    r"rm\s+(-\w*f\w*\s+)?(-\w*r\w*\s+)?/(\s|$)",  # rm -rf / variants
    r"rm\s+(-\w*r\w*\s+)?(-\w*f\w*\s+)?/(\s|$)",
    r"rm\s+.*~",                                     # rm ~ variants
    r"mkfs\b",
    r"dd\s+.*if=/dev/(zero|random|urandom)",
    r":\(\)\s*\{.*\|.*&\s*\}\s*;",                  # fork bomb
    r"\bshutdown\b",
    r"\breboot\b",
    r"\binit\s+[0-6]\b",
    r"chmod\s+(-\w+\s+)?777\s+/",                   # chmod 777 /
    r">\s*/dev/sd[a-z]",                             # overwrite disk
    r"curl\s+.*\|\s*(ba)?sh",                        # curl pipe to shell
    r"wget\s+.*\|\s*(ba)?sh",
]


def run_bash(command: str, timeout: int = 30) -> str:
    """Run a bash command in the current directory."""
    cmd_lower = command.lower().strip()
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, cmd_lower):
            return f"[Blocked] Dangerous command rejected."

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.getcwd(),
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        if not output.strip():
            return f"[OK] Command finished, no output. Exit code: {result.returncode}"
        if len(output) > 5000:
            output = output[:5000] + "\n... (output truncated)"
        return output
    except subprocess.TimeoutExpired:
        return f"[Timeout] Command exceeded {timeout}s"
    except Exception as e:
        return f"[Bash error] {e}"


# ════════════════════════════════════════════════════════════════
# 3. WEB SEARCH & FETCH
# ════════════════════════════════════════════════════════════════

def _get_search_provider() -> str:
    """Determine which search provider to use based on config/env."""
    provider = os.environ.get("LOCALAI_SEARCH_PROVIDER", "auto").lower()
    if provider in ("tavily", "duckduckgo"):
        return provider
    # auto: use Tavily if API key is available, else DuckDuckGo
    if os.environ.get("TAVILY_API_KEY"):
        return "tavily"
    return "duckduckgo"


def _search_tavily(query: str, max_results: int) -> str:
    """Search using Tavily API."""
    try:
        from tavily import TavilyClient
        client = TavilyClient()
        response = client.search(query=query, max_results=max_results)
        results = []
        for r in response.get("results", []):
            title = r.get("title", "")
            url = r.get("url", "")
            content = r.get("content", "")
            results.append(f"**{title}**\n{url}\n{content}\n")
        if not results:
            return f"No results found for: {query}"
        return f"Search results for '{query}' (via Tavily):\n\n" + "\n---\n".join(results)
    except ImportError:
        return "[Error] tavily-python not installed. Run: pip install tavily-python"
    except Exception as e:
        return f"[Search error] {e}"


def _search_duckduckgo(query: str, max_results: int) -> str:
    """Search using DuckDuckGo (no API key required)."""
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(
                    f"**{r['title']}**\n{r['href']}\n{r['body']}\n"
                )
        if not results:
            return f"No results found for: {query}"
        return f"Search results for '{query}':\n\n" + "\n---\n".join(results)
    except ImportError:
        return "[Error] duckduckgo-search not installed. Run: pip install duckduckgo-search"
    except Exception as e:
        return f"[Search error] {e}"


def web_search(query: str, max_results: int = 8) -> str:
    """Search the web using Tavily (if configured) or DuckDuckGo (default)."""
    provider = _get_search_provider()
    if provider == "tavily":
        return _search_tavily(query, max_results)
    return _search_duckduckgo(query, max_results)


def _is_url_safe(url: str) -> bool:
    """Block requests to private/internal networks and non-HTTP schemes."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname or ""
        if not hostname:
            return False
        # Block obvious internal hostnames
        if hostname in ("localhost", "metadata.google.internal"):
            return False
        if hostname.startswith("169.254."):
            return False
        # Resolve and check for private IPs
        import socket
        for info in socket.getaddrinfo(hostname, None):
            addr = info[4][0]
            if ipaddress.ip_address(addr).is_private:
                return False
        return True
    except Exception:
        return False


def fetch_url(url: str) -> str:
    """Fetch content from a URL (extract text, strip HTML)."""
    try:
        if not _is_url_safe(url):
            return f"[Blocked] URL targets a private/internal network: {url}"

        import requests
        from bs4 import BeautifulSoup

        headers = {"User-Agent": "Mozilla/5.0 (compatible; LocalAI/1.0)"}
        resp = requests.get(url, headers=headers, timeout=10, allow_redirects=False)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove script/style
        for tag in soup(["script", "style", "nav", "footer", "iframe"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        # Remove consecutive blank lines
        lines = [l for l in text.splitlines() if l.strip()]
        text = "\n".join(lines)

        if len(text) > 6000:
            text = text[:6000] + "\n... (content truncated)"

        return f"[Content from {url}]\n\n{text}"
    except ImportError:
        return "[Error] requests/beautifulsoup4 not installed. Run: pip install requests beautifulsoup4"
    except Exception as e:
        return f"[Fetch error] {e}"


# ════════════════════════════════════════════════════════════════
# 4. TOOL REGISTRY — schema definitions for LLM
# ════════════════════════════════════════════════════════════════

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file. Use when you need to view code, config, or text files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to file (relative or absolute)"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create a new file or overwrite an existing file. Use when you need to create new code or edit a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path":    {"type": "string", "description": "Path to the file to write"},
                    "content": {"type": "string", "description": "Full content to write to the file"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files/directories. Use to explore project structure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path":      {"type": "string", "description": "Directory to list (default: current directory)"},
                    "recursive": {"type": "boolean", "description": "True to view the full directory tree"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_in_files",
            "description": "Search for text/keywords in project files. Useful for finding where a function, variable, or pattern is used.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query":        {"type": "string", "description": "Text to search for"},
                    "path":         {"type": "string", "description": "Directory to search in (default: current directory)"},
                    "file_pattern": {"type": "string", "description": "File pattern (e.g.: '*.py', '*.js', default: '*')"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_bash",
            "description": "Run a bash/shell command in the current directory. Use for: installing packages, running tests, git commands, building projects, viewing logs...",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to run"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds (default 30)"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search for information on the internet (supports Tavily and DuckDuckGo). Uses Tavily when TAVILY_API_KEY is set, otherwise falls back to DuckDuckGo. Use when you need to: look up docs, find error solutions, research new technologies.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query":       {"type": "string", "description": "Question or keywords to search"},
                    "max_results": {"type": "integer", "description": "Maximum number of results (default 8)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "Fetch and read the content of a web page. Use after web_search to read an article/docs in detail.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL to fetch"},
                },
                "required": ["url"],
            },
        },
    },
]

# Map tool name → function handler
TOOL_HANDLERS: dict[str, Any] = {
    "read_file":       read_file,
    "write_file":      write_file,
    "list_directory":  list_directory,
    "search_in_files": search_in_files,
    "run_bash":        run_bash,
    "web_search":      web_search,
    "fetch_url":       fetch_url,
}


def execute_tool(name: str, arguments: dict) -> str:
    """Call a tool by name with arguments from the LLM."""
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return f"[Error] Tool does not exist: {name}"
    try:
        return handler(**arguments)
    except TypeError as e:
        return f"[Tool parameter error '{name}'] {e}"
    except Exception as e:
        return f"[Tool execution error '{name}'] {e}"
