"""Tests for src.agents.mutation_agent — Mutation testing agent."""

from unittest.mock import MagicMock, patch

from src.agents.mutation_agent import (
    Mutation,
    MutationReport,
    _generate_mutations_for_line,
    generate_mutations,
    run_mutation_test,
)


class TestGenerateMutationsForLine:
    def test_arithmetic_plus_to_minus(self):
        mutations = _generate_mutations_for_line("    x = a + b\n", 1, "test.py")
        arith = [m for m in mutations if m.mutation_type == "arithmetic"]
        assert any("-" in m.mutated for m in arith)

    def test_comparison_eq_to_neq(self):
        mutations = _generate_mutations_for_line("    if x == 5:\n", 1, "test.py")
        comp = [m for m in mutations if m.mutation_type == "comparison"]
        assert any("!=" in m.mutated for m in comp)

    def test_boolean_true_to_false(self):
        mutations = _generate_mutations_for_line("    return True\n", 1, "test.py")
        bools = [m for m in mutations if m.mutation_type == "boolean"]
        assert any("False" in m.mutated for m in bools)

    def test_return_value_mutation(self):
        mutations = _generate_mutations_for_line("    return result\n", 1, "test.py")
        returns = [m for m in mutations if m.mutation_type == "return_value"]
        assert any("None" in m.mutated for m in returns)

    def test_skips_comments(self):
        mutations = _generate_mutations_for_line("    # x = a + b\n", 1, "test.py")
        assert len(mutations) == 0

    def test_skips_imports(self):
        mutations = _generate_mutations_for_line("import os\n", 1, "test.py")
        assert len(mutations) == 0

    def test_skips_blank_lines(self):
        mutations = _generate_mutations_for_line("\n", 1, "test.py")
        assert len(mutations) == 0

    def test_skips_decorators(self):
        mutations = _generate_mutations_for_line("@property\n", 1, "test.py")
        assert len(mutations) == 0


class TestGenerateMutations:
    def test_generates_from_file(self, tmp_path):
        source = tmp_path / "example.py"
        source.write_text(
            "def add(a, b):\n"
            "    return a + b\n"
            "\n"
            "def is_valid(x):\n"
            "    return x == 5\n"
        )
        mutations = generate_mutations(str(source))
        assert len(mutations) > 0

    def test_respects_max_mutations(self, tmp_path):
        source = tmp_path / "example.py"
        lines = ["    x = a + b\n"] * 50
        source.write_text("def f():\n" + "".join(lines))
        mutations = generate_mutations(str(source), max_mutations=5)
        assert len(mutations) <= 5

    def test_nonexistent_file(self):
        mutations = generate_mutations("/nonexistent/file.py")
        assert mutations == []

    def test_empty_file(self, tmp_path):
        source = tmp_path / "empty.py"
        source.write_text("")
        mutations = generate_mutations(str(source))
        assert mutations == []


class TestRunMutationTest:
    def test_detected_mutation(self, tmp_path):
        source = tmp_path / "code.py"
        source.write_text("x = 1 + 2\n")

        mutation = Mutation(
            file_path=str(source),
            line_number=1,
            original="x = 1 + 2\n",
            mutated="x = 1 - 2",
            mutation_type="arithmetic",
        )

        # Mock tests failing (detecting the mutation)
        with patch("src.agents.mutation_agent.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            detected = run_mutation_test(mutation, working_directory=str(tmp_path))

        assert detected is True
        assert mutation.detected is True
        # Original file should be restored
        assert source.read_text() == "x = 1 + 2\n"

    def test_survived_mutation(self, tmp_path):
        source = tmp_path / "code.py"
        source.write_text("x = 1 + 2\n")

        mutation = Mutation(
            file_path=str(source),
            line_number=1,
            original="x = 1 + 2\n",
            mutated="x = 1 - 2",
            mutation_type="arithmetic",
        )

        # Mock tests passing (mutation survived)
        with patch("src.agents.mutation_agent.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            detected = run_mutation_test(mutation, working_directory=str(tmp_path))

        assert detected is False
        assert mutation.detected is False

    def test_restores_file_on_error(self, tmp_path):
        source = tmp_path / "code.py"
        original = "x = 1 + 2\n"
        source.write_text(original)

        mutation = Mutation(
            file_path=str(source),
            line_number=1,
            original="x = 1 + 2\n",
            mutated="x = 1 - 2",
            mutation_type="arithmetic",
        )

        with patch("src.agents.mutation_agent.subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Test runner crashed")
            run_mutation_test(mutation, working_directory=str(tmp_path))

        assert source.read_text() == original


class TestMutationReport:
    def test_detection_rate(self):
        report = MutationReport(total_mutations=10, detected=8, survived=2)
        assert report.detection_rate == 80.0

    def test_detection_rate_zero(self):
        report = MutationReport()
        assert report.detection_rate == 0.0

    def test_survived_mutations_property(self):
        m1 = Mutation("f.py", 1, "a", "b", "test", detected=True)
        m2 = Mutation("f.py", 2, "c", "d", "test", detected=False)
        m3 = Mutation("f.py", 3, "e", "f", "test", detected=False)
        report = MutationReport(
            total_mutations=3, detected=1, survived=2,
            mutations=[m1, m2, m3],
        )
        assert len(report.survived_mutations) == 2
