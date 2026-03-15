"""
agent.py — Core Agent Loop
The heart of LocalAI:
  1. Receive message from user
  2. Call LLM with tools
  3. If LLM wants to call a tool → execute → feed result back to LLM
  4. Repeat until LLM returns a final text response
"""
from __future__ import annotations

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

    @staticmethod
    def _message_to_dict(message) -> dict:
        """Convert an OpenAI SDK message object to a plain dict for history."""
        msg = {"role": message.role}
        if message.content:
            msg["content"] = message.content
        if message.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]
        return msg

    def _trim_history(self):
        """Keep history under a rough token budget by dropping old turns."""
        max_chars = self.config.max_tokens * 3  # ~3 chars/token, conservative
        total = sum(len(str(m.get("content", ""))) for m in self.history)
        while total > max_chars and len(self.history) > 2:
            removed = self.history.pop(0)
            total -= len(str(removed.get("content", "")))

    def _run_agent_loop(self) -> str:
        """
        Tool-calling loop:
        LLM → [tool_call] → execute → LLM → [tool_call] → ... → text response
        """
        iteration = 0
        final_response = ""

        while iteration < self.config.max_iterations:
            iteration += 1

            self._trim_history()

            # Call LLM (stream only when expecting a text reply, not during tool loops)
            use_stream = self.config.stream and iteration > 1 or self.config.stream
            try:
                if use_stream:
                    result = self._run_streaming_turn()
                    if result is not None:
                        # Got a final text response via streaming
                        final_response = result
                        break
                    # result is None means tool calls were handled, continue loop
                    continue
                else:
                    response = self._call_llm(stream=False)
            except Exception as e:
                error_str = str(e)
                if "tool_use_failed" in error_str or "tool call validation" in error_str:
                    display.print_info("Tool call had invalid parameters, retrying...")
                    self.history.append({
                        "role": "user",
                        "content": (
                            "[System] Your previous tool call was rejected by the API: "
                            f"{error_str}. Please retry with correct parameter types."
                        ),
                    })
                    continue
                raise
            message = response.choices[0].message

            # No tool call → AI is returning final text response
            if not message.tool_calls:
                final_response = message.content or ""
                self.history.append({
                    "role": "assistant",
                    "content": final_response
                })
                display.print_assistant_response(final_response)
                break

            # Has tool call → execute each tool
            self._handle_tool_calls(message)

        if iteration >= self.config.max_iterations:
            display.print_error(f"Reached limit of {self.config.max_iterations} iterations.")

        return final_response

    def _run_streaming_turn(self) -> str | None:
        """
        Run one LLM turn with streaming.
        Returns the final text if it's a text response, or None if tool calls were handled.
        """
        stream = self._call_llm(stream=True)

        # Accumulate chunks to detect tool calls vs text
        collected_content = ""
        collected_tool_calls: dict[int, dict] = {}  # index → {id, name, arguments_str}
        started_text_stream = False

        for chunk in stream:
            delta = chunk.choices[0].delta

            # Accumulate tool call deltas
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in collected_tool_calls:
                        collected_tool_calls[idx] = {
                            "id": tc_delta.id or "",
                            "name": tc_delta.function.name if tc_delta.function and tc_delta.function.name else "",
                            "arguments": tc_delta.function.arguments if tc_delta.function and tc_delta.function.arguments else "",
                        }
                    else:
                        if tc_delta.id:
                            collected_tool_calls[idx]["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                collected_tool_calls[idx]["name"] += tc_delta.function.name
                            if tc_delta.function.arguments:
                                collected_tool_calls[idx]["arguments"] += tc_delta.function.arguments

            # Stream text content
            if delta.content:
                if not started_text_stream:
                    display.print_assistant_stream_start()
                    started_text_stream = True
                display.print_stream_chunk(delta.content)
                collected_content += delta.content

        # If we streamed text, finish it
        if started_text_stream:
            display.print_stream_end()

        # Handle tool calls if any
        if collected_tool_calls:
            # Build a fake message-like object for _handle_tool_calls_from_stream
            assistant_msg = {"role": "assistant", "content": collected_content or None}
            tool_calls_list = []
            for idx in sorted(collected_tool_calls.keys()):
                tc = collected_tool_calls[idx]
                tool_calls_list.append({
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": tc["arguments"],
                    },
                })
            assistant_msg["tool_calls"] = tool_calls_list
            self.history.append(assistant_msg)

            # Execute each tool
            for tc in tool_calls_list:
                tool_name = tc["function"]["name"]
                try:
                    arguments = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    arguments = {}

                if self.config.show_tool_calls:
                    display.print_tool_call(tool_name, arguments)

                result = execute_tool(tool_name, arguments)

                if self.config.show_tool_calls:
                    display.print_tool_result(tool_name, result)

                self.history.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })
            return None  # Signal to continue the loop

        # Pure text response
        self.history.append({
            "role": "assistant",
            "content": collected_content
        })
        return collected_content

    def _handle_tool_calls(self, message):
        """Execute tool calls from a non-streamed response message."""
        self.history.append(self._message_to_dict(message))

        for tool_call in message.tool_calls:
            tool_name = tool_call.function.name
            try:
                arguments = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                arguments = {}

            if self.config.show_tool_calls:
                display.print_tool_call(tool_name, arguments)

            result = execute_tool(tool_name, arguments)

            if self.config.show_tool_calls:
                display.print_tool_result(tool_name, result)

            self.history.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

    def _call_llm(self, stream: bool = False):
        """Call LLM API with full conversation history."""
        messages = self._build_messages()

        return self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            stream=stream,
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
