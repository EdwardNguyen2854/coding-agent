"""SKILL.md loader and parser for custom slash commands."""

from pathlib import Path

from coding_agent.project_instructions import find_git_root

DEFAULT_CONFIG_DIR = Path.home() / ".coding-agent"
GLOBAL_SKILL_FILE = DEFAULT_CONFIG_DIR / "SKILL.md"


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


def parse_skills(content: str) -> dict[str, str]:
    """Parse SKILL.md content into a mapping of skill name to instructions.

    Skills are defined as level-2 markdown sections (## skill-name).
    The text under each heading becomes the skill's prompt instructions.
    Skill names are lowercased and spaces replaced with hyphens.

    Args:
        content: Raw SKILL.md file content.

    Returns:
        Dict mapping skill names to their instruction content.
    """
    skills: dict[str, str] = {}
    current_name: str | None = None
    current_lines: list[str] = []

    for line in content.splitlines():
        if line.startswith("## "):
            if current_name is not None:
                skills[current_name] = "\n".join(current_lines).strip()
            current_name = line[3:].strip().lower().replace(" ", "-")
            current_lines = []
        elif current_name is not None:
            current_lines.append(line)

    if current_name is not None:
        skills[current_name] = "\n".join(current_lines).strip()

    return skills


def load_skills(start_path: Path | None = None) -> tuple[dict[str, str], list[str]]:
    """Load skills from project SKILL.md and global SKILL.md.

    Project skills take priority over global skills with the same name.

    Args:
        start_path: Starting path for project skill file search. Defaults to CWD.

    Returns:
        Tuple of (skills dict, list of loaded file paths for logging).
    """
    all_skills: dict[str, str] = {}
    loaded_files: list[str] = []

    # Load global skills first (lower priority)
    if GLOBAL_SKILL_FILE.is_file():
        try:
            content = GLOBAL_SKILL_FILE.read_text(encoding="utf-8")
            all_skills.update(parse_skills(content))
            loaded_files.append(str(GLOBAL_SKILL_FILE))
        except OSError:
            pass

    # Load project skills (higher priority — overrides global)
    project_skill_file = find_project_skill_file(start_path)
    if project_skill_file:
        try:
            content = project_skill_file.read_text(encoding="utf-8")
            all_skills.update(parse_skills(content))
            loaded_files.append(str(project_skill_file))
        except OSError:
            pass

    return all_skills, loaded_files
