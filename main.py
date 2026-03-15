#!/usr/bin/env python3
"""
main.py — Entry point của LocalAI
REPL (Read-Eval-Print Loop) với slash commands.

Cách chạy:
  python main.py                    # Dùng config mặc định
  python main.py --model llama3.2   # Chọn model
  python main.py --base-url https://api.groq.com/openai/v1 --api-key gsk_xxx
"""
import os
import sys
import argparse
from pathlib import Path

# Thêm thư mục hiện tại vào Python path
sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from agent import Agent
import display


def parse_args():
    parser = argparse.ArgumentParser(
        description="LocalAI — Terminal AI assistant chạy local",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ:
  # Dùng Ollama (mặc định)
  python main.py

  # Chọn model khác
  python main.py --model llama3.2:3b

  # Dùng Groq (free, nhanh hơn Ollama)
  python main.py \\
    --base-url https://api.groq.com/openai/v1 \\
    --api-key gsk_xxxx \\
    --model llama-3.3-70b-versatile

  # One-shot (không interactive)
  python main.py --prompt "Giải thích code trong file main.py"
        """,
    )
    parser.add_argument("--model",     "-m", help="Model name (vd: qwen2.5:7b, llama3.2)")
    parser.add_argument("--base-url",  "-u", help="API base URL")
    parser.add_argument("--api-key",   "-k", help="API key (dùng 'ollama' cho Ollama)")
    parser.add_argument("--prompt",    "-p", help="One-shot prompt (không mở interactive session)")
    parser.add_argument("--no-tools",        action="store_true", help="Tắt tool calling")
    parser.add_argument("--no-context",      action="store_true", help="Không tự động đọc codebase context")
    parser.add_argument("--config",          action="store_true", help="Hiện cấu hình và thoát")
    return parser.parse_args()


def handle_slash_command(cmd: str, agent: Agent, config: Config) -> bool:
    """
    Xử lý slash commands.
    Returns: True nếu là slash command đã xử lý, False nếu không phải.
    """
    parts = cmd.strip().split(maxsplit=1)
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if command == "/help":
        display.print_help()
        return True

    elif command == "/clear":
        agent.clear_history()
        return True

    elif command == "/exit" or command == "/quit":
        display.print_info("Tạm biệt! 👋")
        sys.exit(0)

    elif command == "/model":
        if not args:
            display.print_info(f"Model hiện tại: {config.model}")
            display.print_info("Dùng: /model <tên-model>")
        else:
            config.model = args
            # Cập nhật client của agent
            from openai import OpenAI
            agent.client = OpenAI(base_url=config.base_url, api_key=config.api_key)
            agent.config = config
            display.print_success(f"Đã đổi model: {args}")
        return True

    elif command == "/add":
        if not args:
            display.print_error("Dùng: /add <đường-dẫn-file>")
        else:
            agent.add_context_file(args)
        return True

    elif command == "/files":
        display.print_context_files(agent.context_files)
        return True

    elif command == "/config":
        display.print_config(config.show())
        return True

    elif command == "/cd":
        if not args:
            display.print_info(f"Working directory: {os.getcwd()}")
        else:
            agent.change_directory(args)
        return True

    elif command == "/tokens":
        estimate = agent.get_token_estimate()
        display.print_info(f"Ước tính tokens trong history: ~{estimate:,}")
        return True

    elif command == "/save":
        config.save()
        display.print_success(f"Đã lưu config vào ~/.config/localai/config.yaml")
        return True

    return False


def run_interactive(agent: Agent, config: Config):
    """Vòng lặp REPL chính."""
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.history import FileHistory
        from prompt_toolkit.auto_suggest import AutoSuggestFromHistory

        history_file = Path.home() / ".config" / "localai" / "history"
        history_file.parent.mkdir(parents=True, exist_ok=True)

        session = PromptSession(
            history=FileHistory(str(history_file)),
            auto_suggest=AutoSuggestFromHistory(),
        )

        def get_input(prompt_text: str) -> str:
            return session.prompt(prompt_text)

    except ImportError:
        # Fallback nếu không có prompt_toolkit
        def get_input(prompt_text: str) -> str:
            return input(prompt_text)

    display.print_welcome(config.model, config.base_url)
    display.print_info(f"Working directory: {os.getcwd()}")
    display.print_separator()

    while True:
        try:
            # Lấy input từ user
            user_input = get_input("\n[You] › ").strip()

            if not user_input:
                continue

            # Slash commands
            if user_input.startswith("/"):
                handle_slash_command(user_input, agent, config)
                continue

            # Chat với AI
            display.print_user_message(user_input)
            display.print_separator()

            with display.print_thinking():
                pass  # Spinner ngắn để biết AI đang xử lý

            agent.chat(user_input)
            display.print_separator()

        except KeyboardInterrupt:
            display.print_info("\nNhấn Ctrl+C lần nữa hoặc gõ /exit để thoát.")
            try:
                get_input("")
            except (KeyboardInterrupt, EOFError):
                display.print_info("Tạm biệt! 👋")
                break

        except EOFError:
            display.print_info("\nTạm biệt! 👋")
            break

        except Exception as e:
            display.print_error(f"Lỗi: {e}")
            import traceback
            traceback.print_exc()


def run_one_shot(agent: Agent, prompt: str):
    """Chạy một câu hỏi và thoát (không interactive)."""
    display.print_info(f"Prompt: {prompt}")
    display.print_separator()
    agent.chat(prompt)


def main():
    args = parse_args()

    # Load config
    config = Config.load()

    # Override bằng args
    if args.model:
        config.model = args.model
    if args.base_url:
        config.base_url = args.base_url
    if args.api_key:
        config.api_key = args.api_key
    if args.no_context:
        config.auto_context = False

    # Chỉ hiện config
    if args.config:
        display.print_config(config.show())
        return

    # Kiểm tra Ollama có đang chạy không (nếu dùng local)
    if "localhost" in config.base_url or "127.0.0.1" in config.base_url:
        _check_ollama(config)

    # Khởi tạo agent
    agent = Agent(config)

    # One-shot mode
    if args.prompt:
        run_one_shot(agent, args.prompt)
    else:
        run_interactive(agent, config)


def _check_ollama(config: Config):
    """Kiểm tra nhanh Ollama có đang chạy và model có sẵn không."""
    try:
        import requests
        resp = requests.get(
            config.base_url.replace("/v1", "") + "/api/tags",
            timeout=3
        )
        if resp.status_code == 200:
            models = [m["name"] for m in resp.json().get("models", [])]
            model_base = config.model.split(":")[0]
            # Kiểm tra model có sẵn
            if models and not any(model_base in m for m in models):
                display.print_info(
                    f"⚠  Model '{config.model}' chưa được pull. "
                    f"Chạy: ollama pull {config.model}"
                )
                display.print_info(f"   Models hiện có: {', '.join(models[:5])}")
    except Exception:
        display.print_error(
            "Không kết nối được Ollama. Hãy chạy: ollama serve\n"
            "  Hoặc cài Ollama tại: https://ollama.com"
        )


if __name__ == "__main__":
    main()
