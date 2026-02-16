"""Agent - ReAct loop orchestrator."""

import json
from typing import Any

from coding_agent.permissions import PermissionSystem
from coding_agent.tools import execute_tool, get_openai_tools
from coding_agent.utils import truncate_output


class Agent:
    """ReAct agent that orchestrates LLM calls and tool execution."""

    def __init__(self, llm_client, conversation, renderer) -> None:
        """Initialize the agent.

        Args:
            llm_client: LLM client for making API calls
            conversation: ConversationManager for message history
            renderer: Renderer for output
        """
        self.llm_client = llm_client
        self.conversation = conversation
        self.renderer = renderer
        self.max_retries = 3
        self.consecutive_failures = 0
        self.permissions = PermissionSystem(renderer)

    def run(self, user_input: str) -> str:
        """Run the ReAct agent loop until no more tool calls.

        Args:
            user_input: The user's input message

        Returns:
            The final assistant response
        """
        self.conversation.add_message("user", user_input)

        while True:
            messages = self.conversation.get_messages()

            tools = get_openai_tools()
            if tools:
                messages_with_tools = [{"tools": tools}] + messages
            else:
                messages_with_tools = messages

            try:
                for delta in self.llm_client.send_message_stream(messages_with_tools):
                    self.renderer.print_info(delta)
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
                return assistant_message or ""

            for tc in tool_calls:
                self._handle_tool_call(tc)

            self.conversation.add_message(
                "assistant",
                assistant_message or "",
            )

            self.consecutive_failures = 0

    def _handle_tool_call(self, tool_call: Any) -> None:
        """Handle a single tool call.

        Args:
            tool_call: The tool call from LLM response
        """
        tool_name = tool_call.function.name
        try:
            arguments = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            error_msg = f"Invalid JSON in tool arguments: {tool_call.function.arguments}"
            self.conversation.add_message(
                "tool",
                json.dumps({"error": error_msg}),
            )
            self.consecutive_failures += 1

            if self.consecutive_failures >= self.max_retries:
                self.renderer.print_error(
                    f"Max retries ({self.max_retries}) reached. Stopping agent."
                )
            return

        if not self.permissions.check_approval(tool_name, arguments):
            denial_result = {
                "error": "User denied permission to execute this tool",
                "output": "",
            }
            self.conversation.add_message("tool", json.dumps(denial_result))
            return

        result = execute_tool(tool_name, arguments)

        if result.is_error:
            self.consecutive_failures += 1
        else:
            self.consecutive_failures = 0

        tool_result_content = truncate_output(result.output)
        if result.error:
            tool_result_content = json.dumps({"error": result.error, "output": truncate_output(result.output)})

        self.conversation.add_message("tool", tool_result_content)
