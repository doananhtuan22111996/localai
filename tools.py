"""
tools.py — Tất cả tools mà agent có thể gọi
Mỗi tool gồm: schema (mô tả cho LLM) + handler (logic thực thi)
"""
import os
import json
import subprocess
from pathlib import Path
from typing import Any


# ════════════════════════════════════════════════════════════════
# 1. FILE OPERATIONS
# ════════════════════════════════════════════════════════════════

def read_file(path: str) -> str:
    """Đọc nội dung một file."""
    try:
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = Path(os.getcwd()) / p
        if not p.exists():
            return f"[Lỗi] File không tồn tại: {path}"
        size_kb = p.stat().st_size / 1024
        if size_kb > 500:
            return f"[Cảnh báo] File quá lớn ({size_kb:.0f}KB). Hãy đọc từng phần."
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"[Lỗi đọc file] {e}"


def write_file(path: str, content: str) -> str:
    """Ghi nội dung vào file (tạo mới hoặc ghi đè)."""
    try:
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = Path(os.getcwd()) / p
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"[OK] Đã ghi {p.stat().st_size} bytes vào {path}"
    except Exception as e:
        return f"[Lỗi ghi file] {e}"


def list_directory(path: str = ".", recursive: bool = False) -> str:
    """Liệt kê files trong thư mục. recursive=True để xem toàn bộ cây."""
    try:
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = Path(os.getcwd()) / p
        if not p.is_dir():
            return f"[Lỗi] Không phải thư mục: {path}"

        # Các thư mục/file cần bỏ qua
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
        return f"[Lỗi] {e}"


def search_in_files(query: str, path: str = ".", file_pattern: str = "*") -> str:
    """Tìm kiếm text trong các file của thư mục (dùng grep nội bộ)."""
    try:
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = Path(os.getcwd()) / p
        results = []
        count = 0
        for file in sorted(p.rglob(file_pattern)):
            if count > 200:
                results.append("... (dừng tại 200 kết quả)")
                break
            if not file.is_file():
                continue
            # Bỏ qua binary & thư mục ignore
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
            return f"Không tìm thấy '{query}' trong {path}"
        return "\n".join(results)
    except Exception as e:
        return f"[Lỗi search] {e}"


# ════════════════════════════════════════════════════════════════
# 2. BASH / SHELL EXECUTION
# ════════════════════════════════════════════════════════════════

# Lệnh bị chặn vì nguy hiểm
BLOCKED_COMMANDS = [
    "rm -rf /", "rm -rf ~", "mkfs", "dd if=/dev/zero",
    ":(){:|:&};:", "fork bomb", "shutdown", "reboot",
]


def run_bash(command: str, timeout: int = 30) -> str:
    """Chạy một lệnh bash trong thư mục hiện tại."""
    # Safety check đơn giản
    cmd_lower = command.lower()
    for blocked in BLOCKED_COMMANDS:
        if blocked in cmd_lower:
            return f"[Bị chặn] Lệnh nguy hiểm bị từ chối: {blocked}"

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
            return f"[OK] Lệnh chạy xong, không có output. Exit code: {result.returncode}"
        # Giới hạn output dài
        if len(output) > 5000:
            output = output[:5000] + "\n... (output bị cắt bớt)"
        return output
    except subprocess.TimeoutExpired:
        return f"[Timeout] Lệnh chạy quá {timeout}s"
    except Exception as e:
        return f"[Lỗi bash] {e}"


# ════════════════════════════════════════════════════════════════
# 3. WEB SEARCH & FETCH
# ════════════════════════════════════════════════════════════════

def web_search(query: str, max_results: int = 8) -> str:
    """Tìm kiếm trên DuckDuckGo (không cần API key)."""
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(
                    f"**{r['title']}**\n{r['href']}\n{r['body']}\n"
                )
        if not results:
            return f"Không tìm thấy kết quả cho: {query}"
        return f"Kết quả tìm kiếm cho '{query}':\n\n" + "\n---\n".join(results)
    except ImportError:
        return "[Lỗi] Chưa cài duckduckgo-search. Chạy: pip install duckduckgo-search"
    except Exception as e:
        return f"[Lỗi search] {e}"


def fetch_url(url: str) -> str:
    """Tải nội dung một URL (trích xuất text, bỏ HTML)."""
    try:
        import requests
        from bs4 import BeautifulSoup

        headers = {"User-Agent": "Mozilla/5.0 (compatible; LocalAI/1.0)"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Xóa script/style
        for tag in soup(["script", "style", "nav", "footer", "iframe"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        # Bỏ dòng trống liên tiếp
        lines = [l for l in text.splitlines() if l.strip()]
        text = "\n".join(lines)

        if len(text) > 6000:
            text = text[:6000] + "\n... (nội dung bị cắt bớt)"

        return f"[Nội dung từ {url}]\n\n{text}"
    except ImportError:
        return "[Lỗi] Chưa cài requests/beautifulsoup4. Chạy: pip install requests beautifulsoup4"
    except Exception as e:
        return f"[Lỗi fetch] {e}"


# ════════════════════════════════════════════════════════════════
# 4. TOOL REGISTRY — định nghĩa schema cho LLM
# ════════════════════════════════════════════════════════════════

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Đọc nội dung một file. Dùng khi cần xem code, config, hoặc text file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Đường dẫn tới file (tương đối hoặc tuyệt đối)"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Tạo file mới hoặc ghi đè nội dung file đã có. Dùng khi cần tạo code mới hoặc chỉnh sửa file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path":    {"type": "string", "description": "Đường dẫn file cần ghi"},
                    "content": {"type": "string", "description": "Toàn bộ nội dung sẽ ghi vào file"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "Xem danh sách files/thư mục. Dùng để khám phá cấu trúc project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path":      {"type": "string", "description": "Thư mục cần xem (mặc định: thư mục hiện tại)", "default": "."},
                    "recursive": {"type": "boolean", "description": "True để xem toàn bộ cây thư mục", "default": False},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_in_files",
            "description": "Tìm kiếm text/keyword trong các file của project. Hữu ích khi tìm nơi dùng một hàm, biến, hoặc pattern.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query":        {"type": "string", "description": "Text cần tìm"},
                    "path":         {"type": "string", "description": "Thư mục tìm kiếm", "default": "."},
                    "file_pattern": {"type": "string", "description": "Pattern file (vd: '*.py', '*.js')", "default": "*"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_bash",
            "description": "Chạy lệnh bash/shell trong thư mục hiện tại. Dùng để: cài package, chạy tests, git commands, build project, xem logs...",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Lệnh shell cần chạy"},
                    "timeout": {"type": "integer", "description": "Timeout tính bằng giây (mặc định 30)", "default": 30},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Tìm kiếm thông tin trên internet (DuckDuckGo). Dùng khi cần: tra cứu docs, tìm giải pháp lỗi, research công nghệ mới.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query":       {"type": "string", "description": "Câu hỏi hoặc từ khóa cần tìm"},
                    "max_results": {"type": "integer", "description": "Số kết quả tối đa (mặc định 8)", "default": 8},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "Tải và đọc nội dung một trang web. Dùng sau web_search để đọc chi tiết một bài viết/docs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL đầy đủ cần tải"},
                },
                "required": ["url"],
            },
        },
    },
]

# Map tên tool → function handler
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
    """Gọi tool theo tên với arguments từ LLM."""
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return f"[Lỗi] Tool không tồn tại: {name}"
    try:
        return handler(**arguments)
    except TypeError as e:
        return f"[Lỗi tham số tool '{name}'] {e}"
    except Exception as e:
        return f"[Lỗi chạy tool '{name}'] {e}"
