"""SKILL.md loader and parser for custom slash commands."""

from dataclasses import dataclass, field
from pathlib import Path

from coding_agent.config.project_instructions import find_git_root

DEFAULT_CONFIG_DIR = Path.home() / ".coding-agent"
GLOBAL_SKILLS_DIR = DEFAULT_CONFIG_DIR / "skills"


@dataclass
class Skill:
    """Represents a loaded skill with metadata and resources."""
    name: str
    description: str
    instructions: str
    scripts_path: Path | None = None
    references_path: Path | None = None
    assets_path: Path | None = None
    skill_dir: Path | None = None
    # Invocation controls
    disable_model_invocation: bool = False
    user_invocable: bool = True
    # Runtime overrides
    allowed_tools: list[str] = field(default_factory=list)
    model: str | None = None
    # Subagent forking
    context: str | None = None
    agent_type: str | None = None
    # UX
    argument_hint: str | None = None
    hooks: dict = field(default_factory=dict)


def _parse_bool(value: str) -> bool:
    """Parse a YAML boolean string."""
    return value.lower() in ("true", "yes", "1")


def _parse_list(value: str) -> list[str]:
    """Parse a comma-separated or bracket-wrapped list string."""
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_yaml_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from SKILL.md content.

    Args:
        content: Raw SKILL.md file content.

    Returns:
        Tuple of (frontmatter dict, remaining content after frontmatter).
    """
    frontmatter: dict = {}
    remaining_content = content

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            yaml_block = parts[1]
            remaining_content = parts[2]
            for line in yaml_block.strip().splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip()
                    value = value.strip()
                    if key in ("disable-model-invocation", "user-invocable"):
                        frontmatter[key] = _parse_bool(value)
                    elif key == "allowed-tools":
                        frontmatter[key] = _parse_list(value)
                    else:
                        frontmatter[key] = value

    return frontmatter, remaining_content.strip()


def find_project_skill_file(start_path: Path | None = None) -> Path | None:
    """Find SKILL.md in the git root or current working directory.

    Args:
        start_path: Starting path for search. Defaults to CWD.

    Returns:
        Path to SKILL.md or None if not found.
    """
    if start_path is None:
        start_path = Path.cwd()

    git_root = find_git_root(start_path)
    search_root = git_root if git_root else start_path.resolve()

    skill_file = search_root / "SKILL.md"
    if skill_file.is_file():
        return skill_file

    return None


def find_skill_folder(skill_file: Path) -> Path | None:
    """Find the skill folder containing SKILL.md.

    Args:
        skill_file: Path to SKILL.md file.

    Returns:
        Path to the skill folder, or None if not in a skill folder.
    """
    parent = skill_file.parent
    if parent.name == ".coding-agent":
        return parent
    if parent.name == "skills":
        return parent
    if (parent / "SKILL.md").resolve() == skill_file.resolve():
        return parent
    return None


def parse_skills(content: str, skill_folder: Path | None = None) -> dict[str, Skill]:
    """Parse SKILL.md content into a mapping of skill name to Skill objects.

    Each skill folder contains one skill. The skill name comes from the folder name.
    Content is treated as instructions, with special sections (## Instructions, ## Examples)
    parsed as part of the instructions.

    Args:
        content: Raw SKILL.md file content.
        skill_folder: Optional path to skill folder for scripts/references/assets.

    Returns:
        Dict mapping skill names to Skill objects.
    """
    frontmatter, content = parse_yaml_frontmatter(content)
    global_description = frontmatter.get("description", "")

    skill_name = skill_folder.name if skill_folder else "unknown"

    scripts_path = skill_folder / "scripts" if skill_folder else None
    references_path = skill_folder / "references" if skill_folder else None
    assets_path = skill_folder / "assets" if skill_folder else None

    skill = Skill(
        name=skill_name,
        description=global_description,
        instructions=content,
        scripts_path=scripts_path if scripts_path and scripts_path.is_dir() else None,
        references_path=references_path if references_path and references_path.is_dir() else None,
        assets_path=assets_path if assets_path and assets_path.is_dir() else None,
        skill_dir=skill_folder,
        disable_model_invocation=frontmatter.get("disable-model-invocation", False),
        user_invocable=frontmatter.get("user-invocable", True),
        allowed_tools=frontmatter.get("allowed-tools", []),
        model=frontmatter.get("model") or None,
        context=frontmatter.get("context") or None,
        agent_type=frontmatter.get("agent") or None,
        argument_hint=frontmatter.get("argument-hint") or None,
        hooks=frontmatter.get("hooks", {}),
    )

    return {skill_name: skill}


def _load_skills_from_dir(skills_dir: Path, all_skills: dict[str, Skill], loaded_files: list[str]) -> None:
    """Load all skills from a skills directory into all_skills (in-place).

    Args:
        skills_dir: Directory containing skill subdirectories.
        all_skills: Dict to update with loaded skills.
        loaded_files: List to append loaded file paths to.
    """
    if not skills_dir.is_dir():
        return
    for skill_folder in skills_dir.iterdir():
        if skill_folder.is_dir():
            skill_file = skill_folder / "SKILL.md"
            if skill_file.is_file():
                try:
                    content = skill_file.read_text(encoding="utf-8")
                    all_skills.update(parse_skills(content, skill_folder))
                    loaded_files.append(str(skill_file))
                except OSError:
                    pass


def load_skills(start_path: Path | None = None) -> tuple[dict[str, Skill], list[str]]:
    """Load skills from all discovery locations.

    Priority (highest wins): project-local > nested cwd > global.

    Discovery locations:
    - ``~/.coding-agent/skills/<name>/SKILL.md``  (global)
    - ``<git-root>/.coding-agent/skills/<name>/SKILL.md``  (project, nested)
    - ``<cwd>/.coding-agent/skills/<name>/SKILL.md``  (cwd-local, monorepo subdirs)
    - ``<git-root>/SKILL.md``  (legacy single-file project skill)

    Args:
        start_path: Starting path for project skill file search. Defaults to CWD.

    Returns:
        Tuple of (skills dict, list of loaded file paths for logging).
    """
    cwd = start_path or Path.cwd()
    all_skills: dict[str, Skill] = {}
    loaded_files: list[str] = []

    # 1. Global skills (lowest priority)
    _load_skills_from_dir(GLOBAL_SKILLS_DIR, all_skills, loaded_files)

    # 2. Git-root nested skills directory
    git_root = find_git_root(cwd)
    if git_root:
        _load_skills_from_dir(git_root / ".coding-agent" / "skills", all_skills, loaded_files)

    # 3. CWD-local nested skills directory (supports monorepo subdirectories)
    cwd_resolved = cwd.resolve()
    if not git_root or cwd_resolved != git_root.resolve():
        _load_skills_from_dir(cwd_resolved / ".coding-agent" / "skills", all_skills, loaded_files)

    # 4. Legacy single-file project SKILL.md (highest priority, overwrites above)
    project_skill_file = find_project_skill_file(start_path)
    if project_skill_file:
        try:
            content = project_skill_file.read_text(encoding="utf-8")
            skill_folder = find_skill_folder(project_skill_file)
            all_skills.update(parse_skills(content, skill_folder))
            loaded_files.append(str(project_skill_file))
        except OSError:
            pass

    return all_skills, loaded_files
