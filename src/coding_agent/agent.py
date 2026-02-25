"""Agent - ReAct loop orchestrator."""

import json
import logging
import os
from typing import Any

from coding_agent.interrupt import is_interrupted

_log = logging.getLogger(__name__)
from coding_agent.permissions import PermissionSystem
from coding_agent.tools import execute_tool, get_openai_tools
from coding_agent.utils import truncate_output


class Agent:
    """ReAct agent that orchestrates LLM calls and tool execution."""

    def __init__(self, llm_client, conversation, renderer, session_manager=None, session_data=None, config=None, workspace_root: str | None = None) -> None:
        """Initialize the agent.

        Args:
            llm_client: LLM client for making API calls
            conversation: ConversationManager for message history
            renderer: Renderer for output
            session_manager: SessionManager for auto-save (optional)
            session_data: Session data dict for auto-save (optional)
            config: AgentConfig for settings like max_context_tokens (optional)
            workspace_root: Root directory for file tools (defaults to cwd)
        """
        self.llm_client = llm_client
        self.conversation = conversation
        self.renderer = renderer
        self.session_manager = session_manager
        self.session_data = session_data
        self.max_retries = 3
        self.consecutive_failures = 0
        self.permissions = PermissionSystem(renderer)
        self.max_context_tokens = config.max_context_tokens if config else 128000
        self.workspace_root = workspace_root or os.getcwd()

    @staticmethod
    def _has_tool_messages(messages: list[dict]) -> bool:
        """Return True if messages contain any tool call or tool result entries."""
        return any(
            m.get("role") == "tool" or (m.get("role") == "assistant" and m.get("tool_calls"))
            for m in messages
        )

    def _call_llm(self, messages: list[dict], tools: list[dict] | None) -> bool:
        """Stream an LLM completion, retrying with simplified history on tool-format rejection.

        When a model rejects tool-formatted messages (BadRequestError), strips tool
        call/result pairs to plain text and retries without tools.

        Args:
            messages: Conversation messages to send.
            tools: Tool definitions, or None to disable tool calling.

        Returns:
            True on success, False on unrecoverable error.
        """
        try:
            with self.renderer.render_streaming_live() as display:
                display.start_thinking()
                for delta in self.llm_client.send_message_stream(messages, tools=tools):
                    if is_interrupted():
                        break
                    display.update(delta)
            return True
        except ConnectionError as e:
            if "rejected the request" in str(e) and self._has_tool_messages(messages):
                self.renderer.print_info("  Retrying with simplified history (model lacks tool support)...")
                simplified = self.conversation.get_messages_simplified()
                try:
                    with self.renderer.render_streaming_live() as display:
                        display.start_thinking()
                        for delta in self.llm_client.send_message_stream(simplified, tools=None):
                            if is_interrupted():
                                break
                            display.update(delta)
                    return True
                except Exception as retry_err:
                    self.renderer.print_error(f"Error: {str(retry_err)}")
                    return False
            self.renderer.print_error(f"Error: {str(e)}")
            return False

    def run(self, user_input: str) -> str:
        """Run the ReAct agent loop until no more tool calls.

        Args:
            user_input: The user's input message

        Returns:
            The final assistant response
        """
        from coding_agent.interrupt import clear_interrupt, is_interrupted
        clear_interrupt()

        self.conversation.add_message("user", user_input)

        iterations = 0
        max_iterations = 40
        last_tool_sig: str | None = None
        repeated_count = 0
        max_repeated = 4

        while True:
            if is_interrupted():
                self.renderer.print_warning("\nInterrupted! Stopping agent.")
                self.conversation.add_message("assistant", "[Interrupted by user]")
                return ""

            iterations += 1
            if iterations > max_iterations:
                self.renderer.print_warning(
                    f"\nStopped: agent exceeded {max_iterations} iterations without finishing."
                )
                return ""

            # Auto-truncate before every LLM call to prevent context overflow
            self.conversation.truncate_if_needed(max_tokens=self.max_context_tokens)

            messages = self.conversation.get_messages()
            tools = get_openai_tools(self.workspace_root)

            if not self._call_llm(messages, tools):
                return ""

            response = self.llm_client.last_response
            if response is None:
                return ""

            assistant_message = response.choices[0].message.content
            tool_calls = response.choices[0].message.tool_calls

            if not tool_calls:
                self.conversation.add_message("assistant", assistant_message or "")
                self.renderer.console.print()  # blank line after response
                self._save_session()
                return assistant_message or ""

            # Detect identical repeated tool calls (stuck loop)
            tool_sig = str([(tc.function.name, tc.function.arguments) for tc in tool_calls])
            if tool_sig == last_tool_sig:
                repeated_count += 1
                if repeated_count >= max_repeated:
                    self.renderer.print_warning(
                        f"\nStopped: same tool call repeated {max_repeated} times in a row."
                    )
                    return ""
            else:
                repeated_count = 0
                last_tool_sig = tool_sig

            # Add assistant message with tool_calls BEFORE tool results
            self.conversation.add_assistant_tool_call(
                assistant_message or "",
                [{"id": tc.id, "name": tc.function.name, "arguments": tc.function.arguments} for tc in tool_calls]
            )

            for tc in tool_calls:
                if is_interrupted():
                    self.renderer.print_warning("\nInterrupted during tool execution!")
                    self.conversation.add_message("assistant", "[Interrupted by user during tool execution]")
                    return ""
                self._handle_tool_call(tc)

            self.consecutive_failures = 0

    def _handle_tool_call(self, tool_call: Any) -> None:
        """Handle a single tool call.

        Args:
            tool_call: The tool call from LLM response
        """
        tool_name = tool_call.function.name
        tool_id = tool_call.id
        
        try:
            arguments = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            error_msg = f"Invalid JSON in tool arguments: {tool_call.function.arguments}"
            self.conversation.add_message(
                "tool",
                json.dumps({"error": error_msg}),
                tool_call_id=tool_id,
            )
            self.consecutive_failures += 1

            if self.consecutive_failures >= self.max_retries:
                self.renderer.print_error(
                    f"Max retries ({self.max_retries}) reached. Stopping agent."
                )
            return

        self.renderer.render_tool_panel(tool_name, arguments)

        # Show diff preview for file_edit before execution
        if tool_name == "file_edit":
            path = arguments.get("path", "")
            old_string = arguments.get("old_string", "")
            new_string = arguments.get("new_string", "")
            if path and old_string:
                try:
                    from pathlib import Path
                    file_path = Path(path)
                    if file_path.exists():
                        current_content = file_path.read_text(encoding="utf-8")
                        # Apply the replacement to show what will change
                        if old_string in current_content:
                            new_content = current_content.replace(old_string, new_string, 1)
                            self.renderer.render_diff_preview(current_content, new_content, file_path=path)
                except Exception as e:
                    _log.debug("Skipping diff preview for %s: %s", path, e)

        if not self.permissions.check_approval(tool_name, arguments):
            denial_result = {
                "error": "User denied permission to execute this tool",
                "output": "",
            }
            self.conversation.add_message("tool", json.dumps(denial_result), tool_call_id=tool_id)
            self.renderer.print_info("  ✗ denied")
            return

        with self.renderer.status_spinner(f"[dim] Running {tool_name}...[/dim]"):
            result = execute_tool(tool_name, arguments)

        if result.is_error:
            self.renderer.print_error(f"  error: {result.message}")
            tool_result_content = json.dumps({"error": result.message, "output": truncate_output(result.output)})
            self.consecutive_failures += 1
        else:
            self.renderer.print_success("  ✓ done")
            tool_result_content = truncate_output(result.output)
            if result.message:
                tool_result_content = json.dumps({"message": result.message, "output": truncate_output(result.output)})
            self.consecutive_failures = 0

        self.conversation.add_message("tool", tool_result_content, tool_call_id=tool_id)

    def _save_session(self) -> None:
        """Auto-save session after assistant completes a response."""
        if self.session_manager and self.session_data:
            self.session_data["messages"] = self.conversation.get_messages()
            self.session_manager.save(self.session_data)

    def set_session(self, session_manager, session_data) -> None:
        """Set session manager and data for auto-save.
        
        Args:
            session_manager: SessionManager instance
            session_data: Session data dict
        """
        self.session_manager = session_manager
        self.session_data = session_data
