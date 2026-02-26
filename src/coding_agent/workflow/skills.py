from coding_agent.config.skills import Skill, load_skills


class SkillResolver:
    """Resolve and load skills for workflows."""

    def __init__(self):
        self._skills: dict[str, Skill] = {}
        self._load_all_skills()

    def _load_all_skills(self) -> None:
        """Load all available skills."""
        skills, _ = load_skills()
        self._skills = skills

    def get_skill(self, name: str) -> Skill | None:
        """Get skill by name."""
        return self._skills.get(name)

    def list_skills(self) -> list[str]:
        """List all available skill names."""
        return list(self._skills.keys())

    def resolve_skill_for_step(
        self, step_skill: str | None, workflow_skill: str | None
    ) -> Skill | None:
        """Resolve which skill to use for a step."""
        skill_name = step_skill or workflow_skill
        if skill_name:
            return self.get_skill(skill_name)
        return None
