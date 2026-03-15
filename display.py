"""
display.py — Terminal UI với Rich
Xử lý tất cả output: markdown, code blocks, tool calls, errors...
"""
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from rich.rule import Rule
from rich.live import Live
from rich.spinner import Spinner
from rich import box

console = Console()

# ── Color palette ──────────────────────────────────────────────
CLR_USER      = "bold cyan"
CLR_ASSISTANT = "bold green"
CLR_TOOL_NAME = "bold yellow"
CLR_TOOL_OUT  = "dim white"
CLR_ERROR     = "bold red"
CLR_INFO      = "dim cyan"
CLR_SUCCESS   = "bold green"
CLR_SEPARATOR = "dim blue"


def print_welcome(model: str, base_url: str):
    """Màn hình chào khi khởi động."""
    console.print()
    console.print(Panel.fit(
        f"[bold cyan]🤖 LocalAI Terminal[/bold cyan]\n"
        f"[dim]Model: [yellow]{model}[/yellow]  |  "
        f"URL: [blue]{base_url}[/blue][/dim]\n\n"
        f"[dim]Gõ [white]/help[/white] để xem lệnh  •  "
        f"[white]Ctrl+C[/white] để thoát[/dim]",
        border_style="cyan",
        padding=(1, 2),
    ))
    console.print()


def print_help():
    """Hiện danh sách slash commands."""
    console.print(Panel(
        "[bold]Các lệnh đặc biệt:[/bold]\n\n"
        "  [cyan]/help[/cyan]           — Hiện menu này\n"
        "  [cyan]/clear[/cyan]          — Xóa conversation history\n"
        "  [cyan]/model <tên>[/cyan]    — Đổi model (vd: /model llama3.2)\n"
        "  [cyan]/add <file>[/cyan]     — Thêm file vào context\n"
        "  [cyan]/files[/cyan]          — Xem files đang trong context\n"
        "  [cyan]/config[/cyan]         — Xem cấu hình hiện tại\n"
        "  [cyan]/cd <path>[/cyan]      — Đổi working directory\n"
        "  [cyan]/exit[/cyan]           — Thoát\n\n"
        "[dim]Hoặc gõ bất cứ điều gì để chat với AI[/dim]",
        title="[bold cyan]LocalAI Help[/bold cyan]",
        border_style="cyan",
    ))


def print_separator():
    """Đường kẻ phân cách mỏng."""
    console.print(Rule(style=CLR_SEPARATOR))


def print_user_message(message: str):
    """Hiện message của user với style."""
    console.print()
    console.print(f"[{CLR_USER}]You ›[/{CLR_USER}] {message}")


def print_tool_call(tool_name: str, arguments: dict):
    """Thông báo AI đang gọi tool gì."""
    args_str = _format_tool_args(tool_name, arguments)
    console.print(
        f"  [dim]⚡[/dim] [{CLR_TOOL_NAME}]{tool_name}[/{CLR_TOOL_NAME}]"
        f"[dim]({args_str})[/dim]"
    )


def print_tool_result(tool_name: str, result: str, show_output: bool = True):
    """Hiện kết quả tool (có thể ẩn nếu quá dài)."""
    if not show_output:
        return
    lines = result.strip().splitlines()
    preview_lines = 8
    if len(lines) <= preview_lines:
        preview = result.strip()
    else:
        preview = "\n".join(lines[:preview_lines]) + f"\n[dim]... ({len(lines) - preview_lines} dòng nữa)[/dim]"

    console.print(
        Panel(
            Text(preview, style=CLR_TOOL_OUT),
            border_style="dim",
            padding=(0, 1),
            box=box.SIMPLE,
        )
    )


def print_assistant_response(content: str):
    """Render response của AI với Markdown và syntax highlight."""
    console.print()
    console.print(f"[{CLR_ASSISTANT}]AI ›[/{CLR_ASSISTANT}]")
    try:
        console.print(Markdown(content))
    except Exception:
        console.print(content)
    console.print()


def print_assistant_stream_start():
    """Bắt đầu stream response."""
    console.print()
    console.print(f"[{CLR_ASSISTANT}]AI ›[/{CLR_ASSISTANT}]")


def print_stream_chunk(chunk: str):
    """In từng chunk khi stream."""
    console.print(chunk, end="", markup=False)


def print_stream_end():
    """Kết thúc stream."""
    console.print()
    console.print()


def print_error(message: str):
    """Hiện lỗi với màu đỏ."""
    console.print(f"[{CLR_ERROR}]✗ {message}[/{CLR_ERROR}]")


def print_info(message: str):
    """Hiện thông tin phụ."""
    console.print(f"[{CLR_INFO}]ℹ {message}[/{CLR_INFO}]")


def print_success(message: str):
    """Hiện thông báo thành công."""
    console.print(f"[{CLR_SUCCESS}]✓ {message}[/{CLR_SUCCESS}]")


def print_thinking():
    """Hiện spinner khi AI đang suy nghĩ."""
    return console.status("[dim]Đang suy nghĩ...[/dim]", spinner="dots")


def print_context_files(files: list[str]):
    """Hiện danh sách files đang trong context."""
    if not files:
        console.print("[dim]Không có file nào trong context.[/dim]")
        return
    console.print("[bold]Files trong context:[/bold]")
    for f in files:
        console.print(f"  [cyan]•[/cyan] {f}")


def print_config(config_dict: dict):
    """Hiện cấu hình hiện tại."""
    lines = []
    for k, v in config_dict.items():
        lines.append(f"  [cyan]{k}[/cyan]: [white]{v}[/white]")
    console.print(Panel(
        "\n".join(lines),
        title="[bold]Config[/bold]",
        border_style="cyan",
    ))


def _format_tool_args(tool_name: str, args: dict) -> str:
    """Format args gọn để hiển thị."""
    if tool_name == "run_bash":
        cmd = args.get("command", "")
        return f'"{cmd[:60]}{"..." if len(cmd) > 60 else ""}"'
    elif tool_name in ("read_file", "write_file", "fetch_url"):
        key = "path" if "path" in args else "url"
        return f'"{args.get(key, "")}"'
    elif tool_name == "web_search":
        return f'"{args.get("query", "")}"'
    elif tool_name == "list_directory":
        return f'"{args.get("path", ".")}"'
    else:
        return ", ".join(f"{k}={repr(v)[:30]}" for k, v in args.items())
