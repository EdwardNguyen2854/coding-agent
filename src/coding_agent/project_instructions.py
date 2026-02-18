"""Project instructions loader for AGENTS.md and CLAUDE.md files."""

from pathlib import Path

DEFAULT_CONFIG_DIR = Path.home() / ".coding-agent"
GLOBAL_INSTRUCTIONS_FILE = DEFAULT_CONFIG_DIR / "AGENTS.md"


def find_git_root(start_path: Path | None = None) -> Path | None:
    """Find the git root directory by scanning upward for .git folder.
    
    Args:
        start_path: Starting path for search. Defaults to current working directory.
        
    Returns:
        Path to git root or None if not found.
    """
    if start_path is None:
        start_path = Path.cwd()
    
    current = start_path.resolve()
    
    while True:
        if (current / ".git").is_dir():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    
    return None


def find_project_instructions(start_path: Path | None = None) -> tuple[Path | None, str | None]:
    """Find project instructions file (AGENTS.md or CLAUDE.md).
    
    Scans from current working directory upward to git root.
    AGENTS.md takes priority over CLAUDE.md if both exist.
    
    Args:
        start_path: Starting path for search. Defaults to CWD.
        
    Returns:
        Tuple of (file_path, instructions_content) or (None, None) if not found.
    """
    if start_path is None:
        start_path = Path.cwd()
    
    git_root = find_git_root(start_path)
    
    if git_root is None:
        return None, None
    
    candidates = ["AGENTS.md", "CLAUDE.md"]
    
    for candidate in candidates:
        file_path = git_root / candidate
        if file_path.is_file():
            try:
                content = file_path.read_text(encoding="utf-8")
                return file_path, content
            except OSError:
                continue
    
    return None, None


def load_global_instructions() -> str | None:
    """Load global instructions from ~/.coding-agent/AGENTS.md.
    
    Returns:
        Content of global instructions file or None if not found.
    """
    if GLOBAL_INSTRUCTIONS_FILE.is_file():
        try:
            return GLOBAL_INSTRUCTIONS_FILE.read_text(encoding="utf-8")
        except OSError:
            pass
    
    return None


def get_enhanced_system_prompt(default_prompt: str) -> tuple[str, list[str]]:
    """Get system prompt with project and global instructions prepended.
    
    Precedence: Project > Global > Default
    
    Args:
        default_prompt: The default system prompt to enhance.
        
    Returns:
        Tuple of (enhanced_prompt, list of loaded file paths for logging).
    """
    loaded_files: list[str] = []
    parts: list[str] = [default_prompt]
    
    project_path, project_content = find_project_instructions()
    if project_path and project_content:
        parts.insert(0, f"\n\n# Project Instructions\n\n{project_content}")
        loaded_files.append(str(project_path))
    
    global_content = load_global_instructions()
    if global_content:
        parts.insert(0, f"\n\n# Global Instructions\n\n{global_content}")
        loaded_files.append(str(GLOBAL_INSTRUCTIONS_FILE))
    
    enhanced = "\n".join(parts)
    return enhanced, loaded_files
