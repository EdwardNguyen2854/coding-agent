"""Tests for SKILL.md loading and parsing."""

from pathlib import Path
from unittest.mock import patch

import pytest

from coding_agent.skills import find_project_skill_file, load_skills, parse_skills


class TestParseSkills:
    """Tests for parse_skills function."""

    def test_single_skill(self):
        """Parse a single skill section."""
        content = "## review\nReview the code for issues."
        skills = parse_skills(content)
        assert "review" in skills
        assert skills["review"] == "Review the code for issues."

    def test_multiple_skills(self):
        """Parse multiple skill sections."""
        content = "## review\nCheck for bugs.\n\n## deploy\nGuide deployment."
        skills = parse_skills(content)
        assert "review" in skills
        assert "deploy" in skills
        assert skills["review"] == "Check for bugs."
        assert skills["deploy"] == "Guide deployment."

    def test_skill_name_lowercased(self):
        """Skill names are lowercased."""
        content = "## Review\nReview the code."
        skills = parse_skills(content)
        assert "review" in skills
        assert "Review" not in skills

    def test_skill_name_spaces_to_hyphens(self):
        """Spaces in skill names become hyphens."""
        content = "## code review\nReview the code."
        skills = parse_skills(content)
        assert "code-review" in skills

    def test_ignores_level1_headings(self):
        """Level-1 headings are not parsed as skills."""
        content = "# SKILL.md\n\n## review\nReview the code."
        skills = parse_skills(content)
        assert len(skills) == 1
        assert "review" in skills

    def test_ignores_level3_headings(self):
        """Level-3 headings inside a skill are part of its content."""
        content = "## review\nReview the code.\n### subsection\nMore details."
        skills = parse_skills(content)
        assert "review" in skills
        assert "### subsection" in skills["review"]

    def test_empty_content(self):
        """Empty content returns empty dict."""
        assert parse_skills("") == {}

    def test_no_skill_sections(self):
        """Content with no ## headings returns empty dict."""
        assert parse_skills("Just some text with no headings.") == {}

    def test_multiline_skill_content(self):
        """Multiline skill content is preserved."""
        content = "## deploy\nLine 1.\nLine 2.\nLine 3."
        skills = parse_skills(content)
        assert "Line 1." in skills["deploy"]
        assert "Line 2." in skills["deploy"]
        assert "Line 3." in skills["deploy"]

    def test_trailing_whitespace_stripped(self):
        """Leading/trailing whitespace in skill content is stripped."""
        content = "## review\n\nSome content.\n\n"
        skills = parse_skills(content)
        assert skills["review"] == "Some content."


class TestFindProjectSkillFile:
    """Tests for find_project_skill_file function."""

    def test_finds_skill_md_in_git_root(self, tmp_path):
        """Finds SKILL.md when it exists at git root."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text("## review\nReview the code.")

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
        skill_file.write_text("## review\nReview the code.")

        result = find_project_skill_file(tmp_path)
        assert result == skill_file


class TestLoadSkills:
    """Tests for load_skills function."""

    def test_loads_project_skill_file(self, tmp_path):
        """Loads skills from project SKILL.md."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text("## review\nReview the code.")

        with patch("coding_agent.skills.GLOBAL_SKILL_FILE", tmp_path / "nonexistent.md"):
            skills, loaded = load_skills(tmp_path)

        assert "review" in skills
        assert str(skill_file) in loaded

    def test_project_skills_override_global(self, tmp_path):
        """Project skills take priority over global skills."""
        global_file = tmp_path / "global_skill.md"
        global_file.write_text("## review\nGlobal review instructions.")

        git_dir = tmp_path / "project" / ".git"
        git_dir.mkdir(parents=True)
        project_file = tmp_path / "project" / "SKILL.md"
        project_file.write_text("## review\nProject review instructions.")

        with patch("coding_agent.skills.GLOBAL_SKILL_FILE", global_file):
            skills, loaded = load_skills(tmp_path / "project")

        assert skills["review"] == "Project review instructions."
        assert len(loaded) == 2

    def test_returns_empty_when_no_skill_files(self, tmp_path):
        """Returns empty dict when no SKILL.md files exist."""
        with patch("coding_agent.skills.GLOBAL_SKILL_FILE", tmp_path / "nonexistent.md"):
            skills, loaded = load_skills(tmp_path)

        assert skills == {}
        assert loaded == []

    def test_global_skills_loaded_when_no_project_file(self, tmp_path):
        """Global skills are loaded when no project SKILL.md exists."""
        global_file = tmp_path / "global_skill.md"
        global_file.write_text("## deploy\nDeploy the app.")

        with patch("coding_agent.skills.GLOBAL_SKILL_FILE", global_file):
            skills, loaded = load_skills(tmp_path)

        assert "deploy" in skills
        assert str(global_file) in loaded
