"""
agent.py — Core Agent Loop
Đây là trái tim của LocalAI:
  1. Nhận message từ user
  2. Gọi LLM với tools
  3. Nếu LLM muốn gọi tool → execute → đưa kết quả lại cho LLM
  4. Lặp lại cho đến khi LLM trả lời text cuối cùng
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
        self.history: list[dict] = []       # Lịch sử conversation
        self.context_files: list[str] = []  # Files user đã /add
        self._cwd = os.getcwd()             # Working directory

    # ── Public interface ──────────────────────────────────────────

    def chat(self, user_message: str) -> str:
        """
        Gửi message và nhận response (có thể gọi nhiều tools).
        Returns: response text cuối cùng từ AI.
        """
        # Thêm message user vào history
        self.history.append({"role": "user", "content": user_message})

        # Thêm context files vào message nếu có
        if self.context_files:
            context_content = self._load_context_files()
            if context_content:
                # Inject vào message cuối
                self.history[-1]["content"] = (
                    f"{user_message}\n\n"
                    f"[Context files được thêm vào]\n{context_content}"
                )

        response_text = self._run_agent_loop()
        return response_text

    def clear_history(self):
        """Xóa toàn bộ conversation history."""
        self.history = []
        display.print_info("Đã xóa conversation history.")

    def add_context_file(self, path: str):
        """Thêm file vào context (giống /add trong Aider)."""
        from pathlib import Path
        p = Path(path)
        if not p.is_absolute():
            p = Path(self._cwd) / p
        if not p.exists():
            display.print_error(f"File không tồn tại: {path}")
            return
        if str(p) not in self.context_files:
            self.context_files.append(str(p))
            display.print_success(f"Đã thêm: {p.name}")
        else:
            display.print_info(f"File đã có trong context: {p.name}")

    def change_directory(self, path: str):
        """Đổi working directory."""
        from pathlib import Path
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = Path(self._cwd) / p
        if not p.is_dir():
            display.print_error(f"Thư mục không tồn tại: {path}")
            return
        self._cwd = str(p.resolve())
        os.chdir(self._cwd)
        display.print_success(f"Đang ở: {self._cwd}")

    # ── Private: Agent Loop ───────────────────────────────────────

    def _run_agent_loop(self) -> str:
        """
        Vòng lặp tool-calling:
        LLM → [tool_call] → execute → LLM → [tool_call] → ... → text response
        """
        iteration = 0
        final_response = ""

        while iteration < self.config.max_iterations:
            iteration += 1

            # Gọi LLM
            response = self._call_llm()
            message = response.choices[0].message

            # Không có tool call → AI đang trả lời text cuối cùng
            if not message.tool_calls:
                final_response = message.content or ""
                self.history.append({
                    "role": "assistant",
                    "content": final_response
                })

                # Hiện response
                if self.config.stream:
                    display.print_assistant_response(final_response)
                break

            # Có tool call → thực thi từng tool
            self.history.append(message)  # Lưu message với tool_calls

            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}

                # Hiện tool đang được gọi
                if self.config.show_tool_calls:
                    display.print_tool_call(tool_name, arguments)

                # Thực thi tool
                result = execute_tool(tool_name, arguments)

                # Hiện kết quả tool
                if self.config.show_tool_calls:
                    display.print_tool_result(tool_name, result)

                # Thêm kết quả tool vào history
                self.history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

        if iteration >= self.config.max_iterations:
            display.print_error(f"Đạt giới hạn {self.config.max_iterations} iterations.")

        return final_response

    def _call_llm(self):
        """Gọi LLM API với full conversation history."""
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
        """Xây dựng danh sách messages gửi cho LLM."""
        system_prompt = build_system_prompt(
            cwd=self._cwd,
            max_file_size_kb=self.config.max_file_size_kb
        )
        return [
            {"role": "system", "content": system_prompt},
            *self.history,
        ]

    def _load_context_files(self) -> str:
        """Đọc nội dung các context files đã /add."""
        from pathlib import Path
        contents = []
        for fpath in self.context_files:
            try:
                p = Path(fpath)
                if p.exists():
                    content = p.read_text(encoding="utf-8", errors="replace")
                    contents.append(f"--- {p.name} ---\n{content}")
            except Exception as e:
                contents.append(f"--- {fpath} --- [Lỗi đọc: {e}]")
        return "\n\n".join(contents)

    def get_token_estimate(self) -> int:
        """Ước tính số tokens trong history (rough estimate)."""
        total_chars = sum(
            len(str(m.get("content", "")))
            for m in self.history
        )
        return total_chars // 4  # ~4 chars per token
