"""Configuration subpackage."""

from coding_agent.config.agent_persona import AgentPersona, AgentSystem
from coding_agent.config.config import (
    AgentConfig,
    ConfigError,
    DEFAULT_CONFIG_DIR,
    DEFAULT_CONFIG_FILE,
    DEFAULT_DOCS_DIR,
    OLLAMA_DEFAULT_API_BASE,
    SkillSetting,
    SkillsConfig,
    DEFAULT_SKILLS,
    apply_cli_overrides,
    clear_runtime_config,
    ensure_docs_installed,
    get_docs_dir,
    get_runtime_config,
    is_ollama_model,
    load_config,
    set_runtime_config,
)
from coding_agent.config.project_instructions import (
    find_git_root,
    find_project_instructions,
    get_agent_docs_dir,
    get_enhanced_system_prompt,
    get_global_instructions_path,
    load_agent_docs,
    load_global_instructions,
)
from coding_agent.config.skills import (
    DEFAULT_CONFIG_DIR,
    GLOBAL_SKILLS_DIR,
    Skill,
    find_project_skill_file,
    find_skill_folder,
    load_skills,
    parse_skills,
    parse_yaml_frontmatter,
)
from coding_agent.config.utils import truncate_output
