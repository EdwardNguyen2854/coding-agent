"""Tests for SKILL.md loading and parsing."""

from pathlib import Path
from unittest.mock import patch

import pytest

from coding_agent.config.skills import (
    Skill,
    find_project_skill_file,
    load_skills,
    parse_yaml_frontmatter,
    parse_skills,
)


class TestParseYamlFrontmatter:
    """Tests for parse_yaml_frontmatter function."""

    def test_parses_yaml_frontmatter(self):
        """Parse YAML frontmatter from content."""
        content = """---
name: my-skill
description: A test skill
---
# Instructions
Skill content here."""
        frontmatter, remaining = parse_yaml_frontmatter(content)
        assert frontmatter["name"] == "my-skill"
        assert frontmatter["description"] == "A test skill"
        assert "# Instructions" in remaining

    def test_no_frontmatter(self):
        """Returns empty dict when no frontmatter."""
        content = "Some content without frontmatter."
        frontmatter, remaining = parse_yaml_frontmatter(content)
        assert frontmatter == {}
        assert remaining == content

    def test_empty_frontmatter(self):
        """Handles empty frontmatter block."""
        content = "---\n---\n# Instructions\nSkill content."
        frontmatter, remaining = parse_yaml_frontmatter(content)
        assert frontmatter == {}
        assert "# Instructions" in remaining

    def test_parses_bool_fields(self):
        """Parses disable-model-invocation and user-invocable as booleans."""
        content = "---\ndisable-model-invocation: true\nuser-invocable: false\n---\nbody"
        frontmatter, _ = parse_yaml_frontmatter(content)
        assert frontmatter["disable-model-invocation"] is True
        assert frontmatter["user-invocable"] is False

    def test_parses_allowed_tools_comma_list(self):
        """Parses allowed-tools as a list from comma-separated string."""
        content = "---\nallowed-tools: Read, Grep, shell\n---\nbody"
        frontmatter, _ = parse_yaml_frontmatter(content)
        assert frontmatter["allowed-tools"] == ["Read", "Grep", "shell"]

    def test_parses_allowed_tools_bracket_list(self):
        """Parses allowed-tools as a list from bracket-wrapped string."""
        content = "---\nallowed-tools: [Read, Grep]\n---\nbody"
        frontmatter, _ = parse_yaml_frontmatter(content)
        assert frontmatter["allowed-tools"] == ["Read", "Grep"]

    def test_parses_model_and_argument_hint(self):
        """Parses model and argument-hint as strings."""
        content = "---\nmodel: litellm/gpt-4o\nargument-hint: [issue-number]\n---\nbody"
        frontmatter, _ = parse_yaml_frontmatter(content)
        assert frontmatter["model"] == "litellm/gpt-4o"
        assert frontmatter["argument-hint"] == "[issue-number]"


class TestParseSkills:
    """Tests for parse_skills function."""

    def test_parse_from_folder(self):
        """Parse skill from folder - name comes from folder."""
        content = "# Instructions\nReview the code for issues."
        skills = parse_skills(content, None)
        assert "unknown" in skills
        assert isinstance(skills["unknown"], Skill)
        assert "Review the code" in skills["unknown"].instructions

    def test_with_scripts_references_assets_folders(self, tmp_path):
        """Detects scripts, references, and assets folders when present."""
        skill_folder = tmp_path / "review"
        skill_folder.mkdir()
        (skill_folder / "scripts").mkdir()
        (skill_folder / "references").mkdir()
        (skill_folder / "assets").mkdir()

        content = "# Instructions\nReview the code."
        skills = parse_skills(content, skill_folder)

        assert "review" in skills
        assert skills["review"].scripts_path == skill_folder / "scripts"
        assert skills["review"].references_path == skill_folder / "references"
        assert skills["review"].assets_path == skill_folder / "assets"

    def test_paths_none_when_folders_dont_exist(self, tmp_path):
        """Returns None paths when folders don't exist."""
        content = "Instructions here."
        skills = parse_skills(content, tmp_path)

        assert tmp_path.name in skills
        assert skills[tmp_path.name].scripts_path is None
        assert skills[tmp_path.name].references_path is None
        assert skills[tmp_path.name].assets_path is None

    def test_with_yaml_frontmatter(self):
        """Parses skills with YAML frontmatter metadata."""
        content = """---
name: review
description: Code review skill
---
# Instructions
Review code carefully."""
        skills = parse_skills(content, None)
        assert "unknown" in skills
        assert skills["unknown"].description == "Code review skill"
        assert "Review code carefully" in skills["unknown"].instructions

    def test_parses_new_control_fields(self, tmp_path):
        """New frontmatter fields are parsed into Skill attributes."""
        content = (
            "---\n"
            "description: A deployment skill\n"
            "disable-model-invocation: true\n"
            "user-invocable: false\n"
            "allowed-tools: Read, Grep\n"
            "model: litellm/gpt-4o\n"
            "argument-hint: [env]\n"
            "context: fork\n"
            "agent: Explore\n"
            "---\n"
            "Deploy the service."
        )
        skills = parse_skills(content, tmp_path)
        skill = skills[tmp_path.name]
        assert skill.disable_model_invocation is True
        assert skill.user_invocable is False
        assert skill.allowed_tools == ["Read", "Grep"]
        assert skill.model == "litellm/gpt-4o"
        assert skill.argument_hint == "[env]"
        assert skill.context == "fork"
        assert skill.agent_type == "Explore"
        assert skill.skill_dir == tmp_path

    def test_defaults_for_new_fields(self, tmp_path):
        """New fields default to safe values when absent from frontmatter."""
        content = "---\ndescription: Simple skill\n---\nDo something."
        skills = parse_skills(content, tmp_path)
        skill = skills[tmp_path.name]
        assert skill.disable_model_invocation is False
        assert skill.user_invocable is True
        assert skill.allowed_tools == []
        assert skill.model is None
        assert skill.argument_hint is None
        assert skill.context is None
        assert skill.agent_type is None


class TestFindProjectSkillFile:
    """Tests for find_project_skill_file function."""

    def test_finds_skill_md_in_git_root(self, tmp_path):
        """Finds SKILL.md when it exists at git root."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text("# Instructions\nReview the code.")

        result = find_project_skill_file(tmp_path)
        assert result == skill_file

    def test_returns_none_when_no_skill_md(self, tmp_path):
        """Returns None when SKILL.md does not exist."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        result = find_project_skill_file(tmp_path)
        assert result is None

    def test_falls_back_to_cwd_without_git(self, tmp_path):
        """Uses cwd when no git root is found."""
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text("# Instructions\nReview the code.")

        result = find_project_skill_file(tmp_path)
        assert result == skill_file


class TestLoadSkills:
    """Tests for load_skills function."""

    def test_loads_project_skill_file(self, tmp_path):
        """Loads skills from project SKILL.md."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text("# Instructions\nReview the code.")

        with patch("coding_agent.config.skills.GLOBAL_SKILLS_DIR", tmp_path / "nonexistent"):
            skills, loaded = load_skills(tmp_path)

        assert len(skills) >= 1
        assert str(skill_file) in loaded

    def test_project_skills_override_global(self, tmp_path):
        """Project skills take priority over global skills."""
        global_skills_dir = tmp_path / "skills"
        global_skills_dir.mkdir()
        global_skill_folder = global_skills_dir / "review"
        global_skill_folder.mkdir()
        (global_skill_folder / "SKILL.md").write_text("# Instructions\nGlobal review.")

        git_dir = tmp_path / "project" / ".git"
        git_dir.mkdir(parents=True)
        project_file = tmp_path / "project" / "SKILL.md"
        project_file.write_text("# Instructions\nProject review.")

        with patch("coding_agent.config.skills.GLOBAL_SKILLS_DIR", global_skills_dir):
            skills, loaded = load_skills(tmp_path / "project")

        assert len(loaded) == 2

    def test_returns_empty_when_no_skill_files(self, tmp_path):
        """Returns empty dict when no SKILL.md files exist."""
        with patch("coding_agent.config.skills.GLOBAL_SKILLS_DIR", tmp_path / "nonexistent"):
            skills, loaded = load_skills(tmp_path)

        assert skills == {}
        assert loaded == []

    def test_global_skills_loaded_when_no_project_file(self, tmp_path):
        """Global skills are loaded when no project SKILL.md exists."""
        global_skills_dir = tmp_path / "skills"
        global_skills_dir.mkdir()
        global_skill_folder = global_skills_dir / "deploy"
        global_skill_folder.mkdir()
        (global_skill_folder / "SKILL.md").write_text("# Instructions\nDeploy the app.")

        with patch("coding_agent.config.skills.GLOBAL_SKILLS_DIR", global_skills_dir):
            skills, loaded = load_skills(tmp_path)

        assert "deploy" in skills
        assert str(global_skill_folder / "SKILL.md") in loaded

    def test_nested_coding_agent_skills_dir_loaded(self, tmp_path):
        """Skills in <git-root>/.coding-agent/skills/ are discovered."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        nested_skills_dir = tmp_path / ".coding-agent" / "skills" / "lint"
        nested_skills_dir.mkdir(parents=True)
        skill_file = nested_skills_dir / "SKILL.md"
        skill_file.write_text("---\ndescription: Lint skill\n---\nRun linting.")

        with patch("coding_agent.config.skills.GLOBAL_SKILLS_DIR", tmp_path / "nonexistent"):
            skills, loaded = load_skills(tmp_path)

        assert "lint" in skills
        assert str(skill_file) in loaded

    def test_cwd_local_skills_override_global(self, tmp_path):
        """CWD-local .coding-agent/skills/ override global skills with same name."""
        global_skills_dir = tmp_path / "global-skills"
        global_skill = global_skills_dir / "review"
        global_skill.mkdir(parents=True)
        (global_skill / "SKILL.md").write_text("Global review.")

        sub = tmp_path / "sub"
        sub.mkdir()
        local_skill = sub / ".coding-agent" / "skills" / "review"
        local_skill.mkdir(parents=True)
        (local_skill / "SKILL.md").write_text("Local review.")

        with patch("coding_agent.config.skills.GLOBAL_SKILLS_DIR", global_skills_dir):
            skills, _ = load_skills(sub)

        assert "review" in skills
        assert "Local review" in skills["review"].instructions
