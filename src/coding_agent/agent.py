"""Agent - ReAct loop orchestrator."""

import json
from typing import Any

from coding_agent.permissions import PermissionSystem
from coding_agent.tools import execute_tool, get_openai_tools
from coding_agent.utils import truncate_output


class Agent:
    """ReAct agent that orchestrates LLM calls and tool execution."""

    def __init__(self, llm_client, conversation, renderer, session_manager=None, session_data=None, config=None) -> None:
        """Initialize the agent.

        Args:
            llm_client: LLM client for making API calls
            conversation: ConversationManager for message history
            renderer: Renderer for output
            session_manager: SessionManager for auto-save (optional)
            session_data: Session data dict for auto-save (optional)
            config: AgentConfig for settings like max_context_tokens (optional)
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

    def run(self, user_input: str) -> str:
        """Run the ReAct agent loop until no more tool calls.

        Args:
            user_input: The user's input message

        Returns:
            The final assistant response
        """
        self.conversation.add_message("user", user_input)

        while True:
            # Auto-truncate before every LLM call to prevent context overflow
            self.conversation.truncate_if_needed(max_tokens=self.max_context_tokens)
            
            messages = self.conversation.get_messages()

            # Get tools but don't add them to messages - pass separately to LLM
            tools = get_openai_tools()

            try:
                with self.renderer.render_streaming_live() as display:
                    display.start_thinking()
                    for delta in self.llm_client.send_message_stream(messages, tools=tools):
                        display.update(delta)
                    full_text = display.full_text
            except Exception as e:
                self.renderer.print_error(f"Error: {str(e)}")
                return ""

            response = self.llm_client.last_response
            if response is None:
                return ""

            assistant_message = response.choices[0].message.content
            tool_calls = response.choices[0].message.tool_calls

            if not tool_calls:
                self.conversation.add_message("assistant", assistant_message or "")
                self._save_session()
                return assistant_message or ""

            # Add assistant message with tool_calls BEFORE tool results
            self.conversation.add_assistant_tool_call(
                assistant_message or "",
                [{"id": tc.id, "name": tc.function.name, "arguments": tc.function.arguments} for tc in tool_calls]
            )

            for tc in tool_calls:
                self._handle_tool_call(tc)

            self.consecutive_failures = 0
            self.renderer.render_separator()

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
                except Exception:
                    pass  # Silently skip diff if file cannot be read

        if not self.permissions.check_approval(tool_name, arguments):
            denial_result = {
                "error": "User denied permission to execute this tool",
                "output": "",
            }
            self.conversation.add_message("tool", json.dumps(denial_result), tool_call_id=tool_id)
            self.renderer.print_info("  ✗ denied")
            return

        with self.renderer.status_spinner(f"  Running {tool_name}..."):
            result = execute_tool(tool_name, arguments)

        if result.is_error:
            self.renderer.print_error(f"  error: {result.error}")
            tool_result_content = json.dumps({"error": result.error, "output": truncate_output(result.output)})
            self.consecutive_failures += 1
        else:
            self.renderer.print_success("  ✓ done")
            tool_result_content = truncate_output(result.output)
            if result.error:
                tool_result_content = json.dumps({"error": result.error, "output": truncate_output(result.output)})
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
