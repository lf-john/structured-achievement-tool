"""
Tech Stack Detection — Scan a project directory to determine language,
test framework, and test directory.

Pure Python file-system scanning. No LLM calls.
Results are cached per directory (invalidated if mtime changes).
"""

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TechStack:
    """Detected technology stack for a project."""
    language: str = "python"           # python, javascript, php, rust, go, etc.
    test_framework: str = "pytest"     # pytest, jest, phpunit, go test, cargo test
    test_directory: str = "tests/"     # Relative path to test directory
    test_command: str = "pytest"       # Command to run tests
    package_file: str = ""             # requirements.txt, package.json, composer.json
    build_tool: str = ""               # pip, npm, composer, cargo, go


# Marker files → (language, test_framework, test_directory, test_command, build_tool)
_MARKER_FILES = [
    # Python
    ("pyproject.toml",     "python",     "pytest",   "tests/",  "pytest",        "pip"),
    ("setup.py",           "python",     "pytest",   "tests/",  "pytest",        "pip"),
    ("setup.cfg",          "python",     "pytest",   "tests/",  "pytest",        "pip"),
    ("requirements.txt",   "python",     "pytest",   "tests/",  "pytest",        "pip"),
    ("Pipfile",            "python",     "pytest",   "tests/",  "pytest",        "pipenv"),
    # JavaScript / TypeScript
    ("package.json",       "javascript", "jest",     "tests/",  "npm test",      "npm"),
    ("tsconfig.json",      "typescript", "jest",     "tests/",  "npm test",      "npm"),
    ("bun.lockb",          "typescript", "bun:test", "tests/",  "bun test",      "bun"),
    # PHP
    ("composer.json",      "php",        "phpunit",  "tests/",  "vendor/bin/phpunit", "composer"),
    # Rust
    ("Cargo.toml",         "rust",       "cargo",    "tests/",  "cargo test",    "cargo"),
    # Go
    ("go.mod",             "go",         "go",       ".",       "go test ./...", "go"),
]


# Cache: directory → (mtime, TechStack)
_cache: dict[str, tuple[float, TechStack]] = {}


def detect_tech_stack(working_directory: str) -> TechStack:
    """Detect the tech stack of a project by scanning for marker files.

    Checks for package files (requirements.txt, package.json, etc.) and
    infers language, test framework, and test directory.

    Results are cached per directory; cache invalidates if directory mtime changes.

    Args:
        working_directory: Root directory of the project.

    Returns:
        TechStack with detected values, defaults to Python/pytest if nothing found.
    """
    if not os.path.isdir(working_directory):
        return TechStack()

    # Check cache
    try:
        dir_mtime = os.path.getmtime(working_directory)
    except OSError:
        dir_mtime = 0.0

    cached = _cache.get(working_directory)
    if cached and cached[0] == dir_mtime:
        return cached[1]

    # Scan for marker files
    detected = None
    for marker, lang, framework, test_dir, test_cmd, build in _MARKER_FILES:
        if os.path.exists(os.path.join(working_directory, marker)):
            detected = TechStack(
                language=lang,
                test_framework=framework,
                test_directory=test_dir,
                test_command=test_cmd,
                package_file=marker,
                build_tool=build,
            )
            break

    if detected is None:
        detected = TechStack()  # Defaults to python/pytest

    # Refine test directory — check common alternatives
    detected.test_directory = _find_test_directory(working_directory, detected)

    # Refine test framework from config files
    detected = _refine_from_config(working_directory, detected)

    logger.debug(
        f"Tech stack for {working_directory}: "
        f"{detected.language}/{detected.test_framework} "
        f"(tests: {detected.test_directory})"
    )

    _cache[working_directory] = (dir_mtime, detected)
    return detected


def _find_test_directory(working_directory: str, stack: TechStack) -> str:
    """Find the actual test directory by checking common locations."""
    candidates = ["tests/", "test/", "spec/", "__tests__/", "src/tests/"]

    for candidate in candidates:
        path = os.path.join(working_directory, candidate)
        if os.path.isdir(path):
            return candidate

    return stack.test_directory


def _refine_from_config(working_directory: str, stack: TechStack) -> TechStack:
    """Refine detection by reading config file contents.

    Checks pyproject.toml for test tool, package.json for test scripts, etc.
    """
    if stack.language == "python":
        # Check if pytest.ini or tox.ini exists
        if os.path.exists(os.path.join(working_directory, "pytest.ini")):
            stack.test_framework = "pytest"
            stack.test_command = "pytest"
        elif os.path.exists(os.path.join(working_directory, "tox.ini")):
            stack.test_framework = "pytest"
            stack.test_command = "tox"

        # Check pyproject.toml for tool.pytest section
        pyproject = os.path.join(working_directory, "pyproject.toml")
        if os.path.exists(pyproject):
            try:
                with open(pyproject) as f:
                    content = f.read()
                if "[tool.pytest" in content:
                    stack.test_framework = "pytest"
                    stack.test_command = "pytest"
                # Check for testpaths in pytest config
                for line in content.split("\n"):
                    if "testpaths" in line and "=" in line:
                        val = line.split("=", 1)[1].strip().strip('"[]').strip()
                        if val:
                            stack.test_directory = val.strip('"') + "/"
            except Exception:
                pass

    elif stack.language in ("javascript", "typescript"):
        # Check package.json for test script and jest config
        pkg_json = os.path.join(working_directory, "package.json")
        if os.path.exists(pkg_json):
            try:
                import json
                with open(pkg_json) as f:
                    pkg = json.load(f)
                scripts = pkg.get("scripts", {})
                test_script = scripts.get("test", "")
                if "vitest" in test_script:
                    stack.test_framework = "vitest"
                    stack.test_command = "npm test"
                elif "mocha" in test_script:
                    stack.test_framework = "mocha"
                    stack.test_command = "npm test"
                # Check devDependencies
                dev_deps = pkg.get("devDependencies", {})
                if "vitest" in dev_deps:
                    stack.test_framework = "vitest"
                elif "jest" in dev_deps:
                    stack.test_framework = "jest"
            except Exception:
                pass

    return stack


def get_existing_test_files(working_directory: str, test_directory: str) -> list[str]:
    """List existing test files in the test directory.

    Returns relative paths from working_directory.
    """
    test_path = os.path.join(working_directory, test_directory)
    if not os.path.isdir(test_path):
        return []

    test_files = []
    test_extensions = (".test.py", ".test.js", ".test.ts", ".test.php",
                       "_test.py", "_test.go", "_test.rs")
    test_prefixes = ("test_",)

    for root, _dirs, files in os.walk(test_path):
        for f in sorted(files):
            is_test = (
                any(f.endswith(ext) for ext in test_extensions)
                or any(f.startswith(pfx) for pfx in test_prefixes)
            )
            if is_test:
                rel = os.path.relpath(os.path.join(root, f), working_directory)
                test_files.append(rel)

    return test_files
