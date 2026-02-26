from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class AgentPersona:
    name: str
    display_name: str
    title: str
    icon: str
    communication_style: str
    principles: list[str]

    def format_message(self, content: str) -> str:
        """Format message according to persona style."""
        return f"[{self.icon}] {self.display_name}: {content}"

    def format_system_prompt(self) -> str:
        """Format persona as system prompt."""
        lines = [
            f"You are {self.display_name}, {self.title}.",
            "",
            "Communication style:",
            self.communication_style.strip(),
            "",
            "Principles:",
        ]
        for principle in self.principles:
            lines.append(f"- {principle}")
        return "\n".join(lines)


class AgentSystem:
    """Manage agent personas."""

    def __init__(self, config_dir: Path | None = None):
        self.config_dir = config_dir or (Path.home() / ".coding-agent")
        self._personas: dict[str, AgentPersona] = {}
        self._current_agent: AgentPersona | None = None
        self._load_agents()

    def _agents_file(self) -> Path:
        return self.config_dir / "agents.yaml"

    def _load_agents(self) -> None:
        """Load agent personas from config."""
        agents_file = self._agents_file()
        if not agents_file.exists():
            self._load_default_agents()
            return

        try:
            data = yaml.safe_load(agents_file.read_text(encoding="utf-8"))
            if data and "agents" in data:
                for agent_data in data["agents"]:
                    persona = AgentPersona(
                        name=agent_data["name"],
                        display_name=agent_data.get("displayName", agent_data["name"]),
                        title=agent_data.get("title", ""),
                        icon=agent_data.get("icon", "🤖"),
                        communication_style=agent_data.get("communication_style", ""),
                        principles=agent_data.get("principles", []),
                    )
                    self._personas[persona.name] = persona
        except Exception:
            self._load_default_agents()

    def _load_default_agents(self) -> None:
        """Load default built-in agents."""
        try:
            from importlib.resources import files
            pkg = files("coding_agent")
            default_agents = pkg / "config" / "agents.yaml"
            if default_agents.exists():
                data = yaml.safe_load(default_agents.read_text(encoding="utf-8"))
                if data and "agents" in data:
                    for agent_data in data["agents"]:
                        persona = AgentPersona(
                            name=agent_data["name"],
                            display_name=agent_data.get("displayName", agent_data["name"]),
                            title=agent_data.get("title", ""),
                            icon=agent_data.get("icon", "🤖"),
                            communication_style=agent_data.get("communication_style", ""),
                            principles=agent_data.get("principles", []),
                        )
                        self._personas[persona.name] = persona
        except Exception:
            pass

    def get(self, name: str) -> AgentPersona | None:
        """Get agent persona by name."""
        return self._personas.get(name)

    def list_agents(self) -> list[AgentPersona]:
        """List all available agent personas."""
        return list(self._personas.values())

    def switch_agent(self, name: str) -> bool:
        """Switch to a different agent persona.
        
        Args:
            name: Agent name to switch to
            
        Returns:
            True if switch was successful
        """
        persona = self.get(name)
        if persona:
            self._current_agent = persona
            return True
        return False

    @property
    def current_agent(self) -> AgentPersona | None:
        """Get current agent persona."""
        return self._current_agent

    def set_current_agent(self, persona: AgentPersona) -> None:
        """Set current agent persona directly."""
        self._current_agent = persona
