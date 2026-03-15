"""
agent.py — Core Agent Loop
The heart of LocalAI:
  1. Receive message from user
  2. Call LLM with tools
  3. If LLM wants to call a tool → execute → feed result back to LLM
  4. Repeat until LLM returns a final text response
"""
import json
import os
from openai import OpenAI
from config import Config
from context import build_system_prompt
from tools import TOOL_SCHEMAS, execute_tool
import display


class Agent:
    def __init__(self, config: Config):
        self.config = config
        self.client = OpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
        )
        self.history: list[dict] = []       # Conversation history
        self.context_files: list[str] = []  # Files user has /add-ed
        self._cwd = os.getcwd()             # Working directory

    # ── Public interface ──────────────────────────────────────────

    def chat(self, user_message: str) -> str:
        """
        Send message and receive response (may call multiple tools).
        Returns: final response text from AI.
        """
        # Add user message to history
        self.history.append({"role": "user", "content": user_message})

        # Add context files to message if available
        if self.context_files:
            context_content = self._load_context_files()
            if context_content:
                # Inject into last message
                self.history[-1]["content"] = (
                    f"{user_message}\n\n"
                    f"[Context files added]\n{context_content}"
                )

        response_text = self._run_agent_loop()
        return response_text

    def clear_history(self):
        """Clear all conversation history."""
        self.history = []
        display.print_info("Conversation history cleared.")

    def add_context_file(self, path: str):
        """Add file to context (similar to /add in Aider)."""
        from pathlib import Path
        p = Path(path)
        if not p.is_absolute():
            p = Path(self._cwd) / p
        if not p.exists():
            display.print_error(f"File does not exist: {path}")
            return
        if str(p) not in self.context_files:
            self.context_files.append(str(p))
            display.print_success(f"Added: {p.name}")
        else:
            display.print_info(f"File already in context: {p.name}")

    def change_directory(self, path: str):
        """Change working directory."""
        from pathlib import Path
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = Path(self._cwd) / p
        if not p.is_dir():
            display.print_error(f"Directory does not exist: {path}")
            return
        self._cwd = str(p.resolve())
        os.chdir(self._cwd)
        display.print_success(f"Now in: {self._cwd}")

    # ── Private: Agent Loop ───────────────────────────────────────

    def _run_agent_loop(self) -> str:
        """
        Tool-calling loop:
        LLM → [tool_call] → execute → LLM → [tool_call] → ... → text response
        """
        iteration = 0
        final_response = ""

        while iteration < self.config.max_iterations:
            iteration += 1

            # Call LLM
            response = self._call_llm()
            message = response.choices[0].message

            # No tool call → AI is returning final text response
            if not message.tool_calls:
                final_response = message.content or ""
                self.history.append({
                    "role": "assistant",
                    "content": final_response
                })

                # Display response
                if self.config.stream:
                    display.print_assistant_response(final_response)
                break

            # Has tool call → execute each tool
            self.history.append(message)  # Save message with tool_calls

            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}

                # Show tool being called
                if self.config.show_tool_calls:
                    display.print_tool_call(tool_name, arguments)

                # Execute tool
                result = execute_tool(tool_name, arguments)

                # Show tool result
                if self.config.show_tool_calls:
                    display.print_tool_result(tool_name, result)

                # Add tool result to history
                self.history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

        if iteration >= self.config.max_iterations:
            display.print_error(f"Reached limit of {self.config.max_iterations} iterations.")

        return final_response

    def _call_llm(self):
        """Call LLM API with full conversation history."""
        messages = self._build_messages()

        return self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
        )

    def _build_messages(self) -> list[dict]:
        """Build the list of messages to send to the LLM."""
        system_prompt = build_system_prompt(
            cwd=self._cwd,
            max_file_size_kb=self.config.max_file_size_kb
        )
        return [
            {"role": "system", "content": system_prompt},
            *self.history,
        ]

    def _load_context_files(self) -> str:
        """Read the contents of /add-ed context files."""
        from pathlib import Path
        contents = []
        for fpath in self.context_files:
            try:
                p = Path(fpath)
                if p.exists():
                    content = p.read_text(encoding="utf-8", errors="replace")
                    contents.append(f"--- {p.name} ---\n{content}")
            except Exception as e:
                contents.append(f"--- {fpath} --- [Read error: {e}]")
        return "\n\n".join(contents)

    def get_token_estimate(self) -> int:
        """Estimate the number of tokens in history (rough estimate)."""
        total_chars = sum(
            len(str(m.get("content", "")))
            for m in self.history
        )
        return total_chars // 4  # ~4 chars per token
