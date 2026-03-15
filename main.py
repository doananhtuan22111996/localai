#!/usr/bin/env python3
"""
main.py — Entry point for LocalAI
REPL (Read-Eval-Print Loop) with slash commands.

Usage:
  python main.py                    # Use default config
  python main.py --model llama3.2   # Choose model
  python main.py --base-url https://api.groq.com/openai/v1 --api-key gsk_xxx
"""
import os
import sys
import argparse
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from agent import Agent
import display


def parse_args():
    parser = argparse.ArgumentParser(
        description="LocalAI — Local terminal AI assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use Ollama (default)
  python main.py

  # Choose a different model
  python main.py --model llama3.2:3b

  # Use Groq (free, faster than Ollama)
  python main.py \\
    --base-url https://api.groq.com/openai/v1 \\
    --api-key gsk_xxxx \\
    --model llama-3.3-70b-versatile

  # One-shot (non-interactive)
  python main.py --prompt "Explain the code in main.py"
        """,
    )
    parser.add_argument("--model",     "-m", help="Model name (e.g.: qwen2.5:7b, llama3.2)")
    parser.add_argument("--base-url",  "-u", help="API base URL")
    parser.add_argument("--api-key",   "-k", help="API key (use 'ollama' for Ollama)")
    parser.add_argument("--prompt",    "-p", help="One-shot prompt (no interactive session)")
    parser.add_argument("--no-tools",        action="store_true", help="Disable tool calling")
    parser.add_argument("--no-context",      action="store_true", help="Don't auto-read codebase context")
    parser.add_argument("--config",          action="store_true", help="Show configuration and exit")
    return parser.parse_args()


def handle_slash_command(cmd: str, agent: Agent, config: Config) -> bool:
    """
    Handle slash commands.
    Returns: True if a slash command was handled, False otherwise.
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
        display.print_info("Goodbye! 👋")
        sys.exit(0)

    elif command == "/model":
        if not args:
            display.print_info(f"Current model: {config.model}")
            display.print_info("Usage: /model <model-name>")
        else:
            config.model = args
            # Update agent's client
            from openai import OpenAI
            agent.client = OpenAI(base_url=config.base_url, api_key=config.api_key)
            agent.config = config
            display.print_success(f"Switched model: {args}")
        return True

    elif command == "/add":
        if not args:
            display.print_error("Usage: /add <file-path>")
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
        display.print_info(f"Estimated tokens in history: ~{estimate:,}")
        return True

    elif command == "/save":
        config.save()
        display.print_success(f"Config saved to ~/.config/localai/config.yaml")
        return True

    return False


def run_interactive(agent: Agent, config: Config):
    """Main REPL loop."""
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
        # Fallback if prompt_toolkit is not installed
        def get_input(prompt_text: str) -> str:
            return input(prompt_text)

    display.print_welcome(config.model, config.base_url)
    display.print_info(f"Working directory: {os.getcwd()}")
    display.print_separator()

    while True:
        try:
            # Get user input
            user_input = get_input("\n[You] › ").strip()

            if not user_input:
                continue

            # Slash commands
            if user_input.startswith("/"):
                handle_slash_command(user_input, agent, config)
                continue

            # Chat with AI
            display.print_user_message(user_input)
            display.print_separator()

            with display.print_thinking():
                pass  # Brief spinner to indicate AI is processing

            agent.chat(user_input)
            display.print_separator()

        except KeyboardInterrupt:
            display.print_info("\nPress Ctrl+C again or type /exit to quit.")
            try:
                get_input("")
            except (KeyboardInterrupt, EOFError):
                display.print_info("Goodbye! 👋")
                break

        except EOFError:
            display.print_info("\nTạm biệt! 👋")
            break

        except Exception as e:
            display.print_error(f"Error: {e}")
            import traceback
            traceback.print_exc()


def run_one_shot(agent: Agent, prompt: str):
    """Run a single prompt and exit (non-interactive)."""
    display.print_info(f"Prompt: {prompt}")
    display.print_separator()
    agent.chat(prompt)


def main():
    args = parse_args()

    # Load config
    config = Config.load()

    # Override with args
    if args.model:
        config.model = args.model
    if args.base_url:
        config.base_url = args.base_url
    if args.api_key:
        config.api_key = args.api_key
    if args.no_context:
        config.auto_context = False

    # Show config only
    if args.config:
        display.print_config(config.show())
        return

    # Check if Ollama is running (when using local)
    if "localhost" in config.base_url or "127.0.0.1" in config.base_url:
        _check_ollama(config)

    # Initialize agent
    agent = Agent(config)

    # One-shot mode
    if args.prompt:
        run_one_shot(agent, args.prompt)
    else:
        run_interactive(agent, config)


def _check_ollama(config: Config):
    """Quick check if Ollama is running and the model is available."""
    try:
        import requests
        resp = requests.get(
            config.base_url.replace("/v1", "") + "/api/tags",
            timeout=3
        )
        if resp.status_code == 200:
            models = [m["name"] for m in resp.json().get("models", [])]
            model_base = config.model.split(":")[0]
            # Check if model is available
            if models and not any(model_base in m for m in models):
                display.print_info(
                    f"⚠  Model '{config.model}' has not been pulled. "
                    f"Run: ollama pull {config.model}"
                )
                display.print_info(f"   Available models: {', '.join(models[:5])}")
    except Exception:
        display.print_error(
            "Cannot connect to Ollama. Run: ollama serve\n"
            "  Or install Ollama at: https://ollama.com"
        )


if __name__ == "__main__":
    main()
