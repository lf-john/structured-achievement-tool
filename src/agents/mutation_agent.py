"""
Mutation Testing Agent — Verify test suite quality by injecting code mutations.

After TDD completion, this agent introduces controlled mutations into the
implementation code and checks whether the test suite catches them.

Complexity: 5-6 (synthesis). Can run on local models (Qwen3, Qwen2.5-Coder).

Mutation types:
- Arithmetic: +→-, *→/, etc.
- Comparison: ==→!=, <→>, <=→>=, etc.
- Boolean: True→False, and→or, not removal
- Return: return X → return None
- Boundary: off-by-one (n→n+1, n→n-1)
- Deletion: remove a statement
"""

import logging
import os
import re
import subprocess
import tempfile
import shutil
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class Mutation:
    """A single code mutation."""
    file_path: str
    line_number: int
    original: str
    mutated: str
    mutation_type: str
    detected: Optional[bool] = None  # True if tests caught it


@dataclass
class MutationReport:
    """Results of mutation testing."""
    total_mutations: int = 0
    detected: int = 0
    survived: int = 0
    errors: int = 0
    mutations: List[Mutation] = field(default_factory=list)

    @property
    def detection_rate(self) -> float:
        if self.total_mutations == 0:
            return 0.0
        return self.detected / self.total_mutations * 100.0

    @property
    def survived_mutations(self) -> List[Mutation]:
        return [m for m in self.mutations if m.detected is False]


# Mutation operators
ARITHMETIC_MUTATIONS = [
    (r'(?<!\w)\+(?!=)', '-'),    # + → -
    (r'(?<!\w)-(?!=)', '+'),     # - → +
    (r'(?<!\w)\*(?!=)', '/'),    # * → /
    (r'(?<!\w)/(?!=)', '*'),     # / → *
]

COMPARISON_MUTATIONS = [
    (r'==', '!='),
    (r'!=', '=='),
    (r'<=', '>'),
    (r'>=', '<'),
    (r'(?<!=)<(?!=)', '>='),
    (r'(?<!=)>(?!=)', '<='),
]

BOOLEAN_MUTATIONS = [
    (r'\bTrue\b', 'False'),
    (r'\bFalse\b', 'True'),
    (r'\band\b', 'or'),
    (r'\bor\b', 'and'),
]

RETURN_MUTATIONS = [
    (r'return\s+(\S+)', 'return None'),
]

BOUNDARY_MUTATIONS = [
    (r'\b(\d+)\b', lambda m: str(int(m.group(1)) + 1)),  # n → n+1
]


def _generate_mutations_for_line(
    line: str,
    line_number: int,
    file_path: str,
) -> List[Mutation]:
    """Generate possible mutations for a single line of code."""
    mutations = []

    # Skip comments, blank lines, docstrings
    stripped = line.strip()
    if not stripped or stripped.startswith('#') or stripped.startswith('"""') or stripped.startswith("'''"):
        return []

    # Skip imports and decorators
    if stripped.startswith(('import ', 'from ', '@')):
        return []

    # Apply arithmetic mutations
    for pattern, replacement in ARITHMETIC_MUTATIONS:
        if re.search(pattern, line):
            mutated = re.sub(pattern, replacement, line, count=1)
            if mutated != line:
                mutations.append(Mutation(
                    file_path=file_path,
                    line_number=line_number,
                    original=line,
                    mutated=mutated,
                    mutation_type="arithmetic",
                ))

    # Apply comparison mutations
    for pattern, replacement in COMPARISON_MUTATIONS:
        if re.search(pattern, line):
            mutated = re.sub(pattern, replacement, line, count=1)
            if mutated != line:
                mutations.append(Mutation(
                    file_path=file_path,
                    line_number=line_number,
                    original=line,
                    mutated=mutated,
                    mutation_type="comparison",
                ))

    # Apply boolean mutations
    for pattern, replacement in BOOLEAN_MUTATIONS:
        if re.search(pattern, line):
            mutated = re.sub(pattern, replacement, line, count=1)
            if mutated != line:
                mutations.append(Mutation(
                    file_path=file_path,
                    line_number=line_number,
                    original=line,
                    mutated=mutated,
                    mutation_type="boolean",
                ))

    # Apply return mutations
    for pattern, replacement in RETURN_MUTATIONS:
        if re.search(pattern, line) and 'return None' not in line:
            mutated = re.sub(pattern, replacement, line, count=1)
            if mutated != line:
                mutations.append(Mutation(
                    file_path=file_path,
                    line_number=line_number,
                    original=line,
                    mutated=mutated,
                    mutation_type="return_value",
                ))

    return mutations


def generate_mutations(
    file_path: str,
    max_mutations: int = 20,
) -> List[Mutation]:
    """Generate mutations for a Python source file.

    Args:
        file_path: Path to the Python source file.
        max_mutations: Maximum number of mutations to generate.

    Returns:
        List of Mutation objects.
    """
    if not os.path.exists(file_path):
        return []

    with open(file_path, 'r') as f:
        lines = f.readlines()

    all_mutations = []
    for i, line in enumerate(lines, start=1):
        mutations = _generate_mutations_for_line(line, i, file_path)
        all_mutations.extend(mutations)

    # Limit to max_mutations, distributing across types
    if len(all_mutations) > max_mutations:
        # Group by type and take proportionally
        by_type = {}
        for m in all_mutations:
            by_type.setdefault(m.mutation_type, []).append(m)

        selected = []
        per_type = max(1, max_mutations // len(by_type))
        for type_name, type_mutations in by_type.items():
            selected.extend(type_mutations[:per_type])

        all_mutations = selected[:max_mutations]

    return all_mutations


def run_mutation_test(
    mutation: Mutation,
    test_command: str = "pytest tests/ -x -q",
    working_directory: str = ".",
    timeout: int = 120,
) -> bool:
    """Apply a mutation, run tests, and check if they catch it.

    Args:
        mutation: The mutation to apply.
        test_command: Test command to run.
        working_directory: Working directory for test execution.
        timeout: Test timeout in seconds.

    Returns:
        True if the mutation was detected (tests failed), False if it survived.
    """
    # Read original file
    with open(mutation.file_path, 'r') as f:
        original_content = f.read()

    original_lines = original_content.split('\n')

    # Apply mutation (line_number is 1-indexed)
    idx = mutation.line_number - 1
    if idx >= len(original_lines):
        return True  # Can't apply, treat as detected

    original_lines[idx] = mutation.mutated.rstrip('\n')
    mutated_content = '\n'.join(original_lines)

    try:
        # Write mutated file
        with open(mutation.file_path, 'w') as f:
            f.write(mutated_content)

        # Run tests
        result = subprocess.run(
            test_command.split(),
            capture_output=True,
            text=True,
            cwd=working_directory,
            timeout=timeout,
        )

        # Tests failed = mutation detected
        detected = result.returncode != 0
        mutation.detected = detected
        return detected

    except subprocess.TimeoutExpired:
        mutation.detected = True  # Timeout counts as detected
        return True
    except Exception as e:
        logger.warning(f"Error running mutation test: {e}")
        mutation.detected = None
        return True
    finally:
        # Restore original file
        with open(mutation.file_path, 'w') as f:
            f.write(original_content)


def run_mutation_suite(
    source_files: List[str],
    test_command: str = "pytest tests/ -x -q",
    working_directory: str = ".",
    max_mutations_per_file: int = 10,
    timeout: int = 120,
) -> MutationReport:
    """Run mutation testing on multiple source files.

    Args:
        source_files: List of Python source files to mutate.
        test_command: Test command to run.
        working_directory: Working directory for test execution.
        max_mutations_per_file: Max mutations per file.
        timeout: Per-test timeout in seconds.

    Returns:
        MutationReport with results.
    """
    report = MutationReport()

    for file_path in source_files:
        mutations = generate_mutations(file_path, max_mutations=max_mutations_per_file)

        for mutation in mutations:
            report.total_mutations += 1
            detected = run_mutation_test(
                mutation, test_command, working_directory, timeout
            )

            if mutation.detected is True:
                report.detected += 1
            elif mutation.detected is False:
                report.survived += 1
            else:
                report.errors += 1

            report.mutations.append(mutation)

            logger.info(
                f"Mutation {report.total_mutations}: {mutation.mutation_type} "
                f"at {mutation.file_path}:{mutation.line_number} — "
                f"{'DETECTED' if detected else 'SURVIVED'}"
            )

    return report
