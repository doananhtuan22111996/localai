"""
context.py — Build system prompt with context from the current directory
The agent needs to know where it is, what project it's in, and what tech stack is used.
"""
import os
import subprocess
from pathlib import Path
from datetime import datetime


# Common code file extensions (prioritized for reading)
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java",
    ".c", ".cpp", ".h", ".cs", ".rb", ".php", ".swift", ".kt",
    ".vue", ".svelte", ".html", ".css", ".scss",
    ".json", ".yaml", ".yml", ".toml", ".env.example",
    ".md", ".txt", ".sh", ".dockerfile", "Dockerfile",
    ".sql", ".graphql",
}

# Special files — always read as they contain important project info
PRIORITY_FILES = {
    "README.md", "README.rst", "package.json", "pyproject.toml",
    "setup.py", "requirements.txt", "go.mod", "Cargo.toml",
    "Makefile", "docker-compose.yml", "docker-compose.yaml",
    ".env.example", "tsconfig.json", "vite.config.js",
    "vite.config.ts", "next.config.js", "next.config.ts",
}

IGNORE_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", "env",
    "dist", "build", ".next", ".cache", ".pytest_cache", "coverage",
    ".mypy_cache", ".ruff_cache", "*.egg-info",
}


def _get_git_info() -> str:
    """Get git info: branch, recent commits, staged files."""
    info_parts = []
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL, text=True
        ).strip()
        info_parts.append(f"Branch: {branch}")
    except Exception:
        return ""

    try:
        log = subprocess.check_output(
            ["git", "log", "--oneline", "-5"],
            stderr=subprocess.DEVNULL, text=True
        ).strip()
        if log:
            info_parts.append(f"Recent commits:\n{log}")
    except Exception:
        pass

    try:
        status = subprocess.check_output(
            ["git", "status", "--short"],
            stderr=subprocess.DEVNULL, text=True
        ).strip()
        if status:
            info_parts.append(f"Changed files:\n{status}")
    except Exception:
        pass

    return "\n".join(info_parts) if info_parts else ""


def _get_project_tree(root: Path, max_depth: int = 3) -> str:
    """Create a compact directory tree (skipping node_modules, .git, ...)."""
    lines = []

    def walk(path: Path, depth: int, prefix: str = ""):
        if depth > max_depth:
            return
        try:
            items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name))
        except PermissionError:
            return

        visible = [
            item for item in items
            if item.name not in IGNORE_DIRS
            and not item.name.startswith(".")
            and not item.name.endswith((".pyc", ".pyo"))
        ]

        for i, item in enumerate(visible[:30]):  # Limit 30 items per level
            is_last = i == len(visible) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{item.name}{'/' if item.is_dir() else ''}")
            if item.is_dir():
                extension = "    " if is_last else "│   "
                walk(item, depth + 1, prefix + extension)

    lines.append(f"{root.name}/")
    walk(root, 1)
    return "\n".join(lines)


def _read_priority_files(root: Path, max_size_kb: int = 150) -> str:
    """Read important files like README, package.json, requirements.txt..."""
    contents = []
    for filename in PRIORITY_FILES:
        fpath = root / filename
        if fpath.exists() and fpath.is_file():
            size_kb = fpath.stat().st_size / 1024
            if size_kb <= max_size_kb:
                try:
                    content = fpath.read_text(encoding="utf-8", errors="replace")
                    if len(content) > 3000:
                        content = content[:3000] + "\n... (truncated)"
                    contents.append(f"=== {filename} ===\n{content}")
                except Exception:
                    pass
    return "\n\n".join(contents)


def _detect_tech_stack(root: Path) -> list[str]:
    """Detect tech stack from indicator files."""
    stack = []
    checks = {
        "Python":     ["requirements.txt", "pyproject.toml", "setup.py", "*.py"],
        "Node.js":    ["package.json", "node_modules"],
        "TypeScript": ["tsconfig.json"],
        "React":      ["src/App.jsx", "src/App.tsx"],
        "Next.js":    ["next.config.js", "next.config.ts", "next.config.mjs"],
        "Vue.js":     ["vue.config.js", "vite.config.js"],
        "Go":         ["go.mod", "go.sum"],
        "Rust":       ["Cargo.toml", "Cargo.lock"],
        "Docker":     ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"],
        "Git":        [".git"],
    }
    for tech, indicators in checks.items():
        for indicator in indicators:
            if "*" in indicator:
                ext = indicator.replace("*", "")
                if any(root.glob(f"*{ext}")):
                    stack.append(tech)
                    break
            elif (root / indicator).exists():
                stack.append(tech)
                break
    return stack


def build_system_prompt(cwd: str = None, max_file_size_kb: int = 150) -> str:
    """
    Build a complete system prompt with context about the current project.
    This is the most important part — helps the AI "understand" where it's working.
    """
    root = Path(cwd or os.getcwd()).resolve()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Gather information
    tech_stack = _detect_tech_stack(root)
    git_info = _get_git_info()
    project_tree = _get_project_tree(root)
    priority_files = _read_priority_files(root, max_file_size_kb)

    # Build prompt
    prompt = f"""You are a local AI assistant running in the terminal, similar to Claude Code.
You are smart, precise, and always think step by step before acting.

━━━ CONTEXT ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 Time: {now}
📁 Working directory: {root}
"""

    if tech_stack:
        prompt += f"🔧 Tech stack: {', '.join(tech_stack)}\n"

    if git_info:
        prompt += f"\n📋 Git info:\n{git_info}\n"

    prompt += f"""
━━━ PROJECT STRUCTURE ━━━━━━━━━━━━━━━━━━━━━━━
{project_tree}
"""

    if priority_files:
        prompt += f"""
━━━ KEY FILES ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{priority_files}
"""

    prompt += """
━━━ INSTRUCTIONS ━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOOLS you can use:
  • read_file        — read any file
  • write_file       — create or edit a file
  • list_directory   — explore directory structure
  • search_in_files  — search text in the codebase
  • run_bash         — run terminal commands (git, npm, pip, pytest...)
  • web_search       — search Google/DuckDuckGo
  • fetch_url        — read web page content

PRINCIPLES:
  1. Always read a file before editing it (use read_file)
  2. When unsure — ask or use list_directory to explore
  3. After editing code — run tests if available
  4. Clearly explain what you're doing and why
  5. If there's an error — read the error carefully, debug step by step

Start by analyzing the user's request and planning before taking action.
"""
    return prompt
