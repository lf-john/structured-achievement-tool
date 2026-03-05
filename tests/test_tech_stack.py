"""Tests for src.execution.tech_stack — Tech stack detection."""

import json

from src.execution.tech_stack import (
    _cache,
    detect_tech_stack,
    get_existing_test_files,
)


class TestDetectTechStack:
    """Test tech stack detection from marker files."""

    def setup_method(self):
        _cache.clear()

    def test_python_requirements_txt(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("pytest\nflask\n")
        (tmp_path / "tests").mkdir()
        stack = detect_tech_stack(str(tmp_path))
        assert stack.language == "python"
        assert stack.test_framework == "pytest"
        assert stack.test_directory == "tests/"

    def test_python_pyproject_toml(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text('[tool.pytest.ini_options]\ntestpaths = ["tests"]')
        (tmp_path / "tests").mkdir()
        stack = detect_tech_stack(str(tmp_path))
        assert stack.language == "python"
        assert stack.test_framework == "pytest"

    def test_javascript_package_json(self, tmp_path):
        pkg = {"scripts": {"test": "jest"}, "devDependencies": {"jest": "^29.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        (tmp_path / "tests").mkdir()
        stack = detect_tech_stack(str(tmp_path))
        assert stack.language == "javascript"
        assert stack.test_framework == "jest"

    def test_javascript_vitest(self, tmp_path):
        pkg = {"scripts": {"test": "vitest run"}, "devDependencies": {"vitest": "^1.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        stack = detect_tech_stack(str(tmp_path))
        assert stack.language == "javascript"
        assert stack.test_framework == "vitest"

    def test_php_composer(self, tmp_path):
        (tmp_path / "composer.json").write_text('{"require": {}}')
        stack = detect_tech_stack(str(tmp_path))
        assert stack.language == "php"
        assert stack.test_framework == "phpunit"

    def test_rust_cargo(self, tmp_path):
        (tmp_path / "Cargo.toml").write_text("[package]\nname = 'test'")
        stack = detect_tech_stack(str(tmp_path))
        assert stack.language == "rust"
        assert stack.test_framework == "cargo"

    def test_go_mod(self, tmp_path):
        (tmp_path / "go.mod").write_text("module example.com/test")
        stack = detect_tech_stack(str(tmp_path))
        assert stack.language == "go"
        assert stack.test_framework == "go"

    def test_defaults_to_python(self, tmp_path):
        # Empty directory — no marker files
        stack = detect_tech_stack(str(tmp_path))
        assert stack.language == "python"
        assert stack.test_framework == "pytest"

    def test_nonexistent_directory(self):
        stack = detect_tech_stack("/nonexistent/path")
        assert stack.language == "python"

    def test_finds_test_directory(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("pytest")
        (tmp_path / "test").mkdir()  # "test/" instead of "tests/"
        stack = detect_tech_stack(str(tmp_path))
        assert stack.test_directory == "test/"

    def test_finds_spec_directory(self, tmp_path):
        pkg = {"scripts": {"test": "jest"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        (tmp_path / "spec").mkdir()
        stack = detect_tech_stack(str(tmp_path))
        assert stack.test_directory == "spec/"

    def test_caching(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("pytest")
        (tmp_path / "tests").mkdir()
        s1 = detect_tech_stack(str(tmp_path))
        s2 = detect_tech_stack(str(tmp_path))
        assert s1 is s2  # Same object from cache


class TestGetExistingTestFiles:
    """Test listing existing test files."""

    def test_finds_test_files(self, tmp_path):
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        (test_dir / "test_foo.py").write_text("def test_x(): pass")
        (test_dir / "test_bar.py").write_text("def test_y(): pass")
        (test_dir / "conftest.py").write_text("")  # Not a test file
        files = get_existing_test_files(str(tmp_path), "tests/")
        assert "tests/test_bar.py" in files
        assert "tests/test_foo.py" in files
        assert "tests/conftest.py" not in files

    def test_finds_dot_test_files(self, tmp_path):
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        (test_dir / "US-001_calc.test.py").write_text("")
        (test_dir / "US-002_auth.test.js").write_text("")
        files = get_existing_test_files(str(tmp_path), "tests/")
        assert len(files) == 2

    def test_empty_directory(self, tmp_path):
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        files = get_existing_test_files(str(tmp_path), "tests/")
        assert files == []

    def test_nonexistent_directory(self, tmp_path):
        files = get_existing_test_files(str(tmp_path), "tests/")
        assert files == []
