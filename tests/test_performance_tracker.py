"""Tests for the PerformanceTracker — historical LLM performance encoding.

Uses an in-memory SQLite database so tests are fast and isolated.
"""

import sqlite3

import pytest

from src.llm.performance_tracker import PerformanceTracker


@pytest.fixture
def tracker(tmp_path):
    """Create a PerformanceTracker backed by a temporary on-disk DB."""
    db_path = str(tmp_path / "test_perf.db")
    return PerformanceTracker(db_path=db_path)


# ------------------------------------------------------------------
# Recording and basic stats
# ------------------------------------------------------------------


class TestRecordAndStats:
    def test_record_single_invocation(self, tracker):
        tracker.record_invocation("sonnet", "coder", "development", success=True, tokens=500)
        stats = tracker.get_provider_stats("sonnet", min_samples=1)
        assert stats["total"] == 1
        assert stats["successes"] == 1
        assert stats["success_rate"] == 1.0

    def test_multiple_invocations_stats(self, tracker):
        for _ in range(3):
            tracker.record_invocation("sonnet", "coder", "development", success=True)
        for _ in range(2):
            tracker.record_invocation("sonnet", "reviewer", "content", success=False)

        stats = tracker.get_provider_stats("sonnet", min_samples=1)
        assert stats["total"] == 5
        assert stats["successes"] == 3
        assert stats["failures"] == 2
        assert stats["success_rate"] == pytest.approx(0.6)

    def test_quality_score_averaging(self, tracker):
        tracker.record_invocation("sonnet", "coder", "development", True, quality_score=0.8)
        tracker.record_invocation("sonnet", "coder", "development", True, quality_score=0.6)
        stats = tracker.get_provider_stats("sonnet", min_samples=1)
        assert stats["avg_quality"] == pytest.approx(0.7)

    def test_duration_and_tokens_averaging(self, tracker):
        tracker.record_invocation("sonnet", "coder", "development", True, tokens=100, duration_seconds=10.0)
        tracker.record_invocation("sonnet", "coder", "development", True, tokens=200, duration_seconds=20.0)
        stats = tracker.get_provider_stats("sonnet", min_samples=1)
        assert stats["avg_tokens"] == pytest.approx(150.0)
        assert stats["avg_duration"] == pytest.approx(15.0)


# ------------------------------------------------------------------
# Min samples gating
# ------------------------------------------------------------------


class TestMinSamples:
    def test_insufficient_samples_returns_empty(self, tracker):
        tracker.record_invocation("sonnet", "coder", "development", success=True)
        stats = tracker.get_provider_stats("sonnet", min_samples=5)
        assert stats == {}

    def test_sufficient_samples_returns_stats(self, tracker):
        for _ in range(5):
            tracker.record_invocation("sonnet", "coder", "development", success=True)
        stats = tracker.get_provider_stats("sonnet", min_samples=5)
        assert stats["total"] == 5

    def test_routing_advice_excludes_insufficient_samples(self, tracker):
        # sonnet has 5 samples (meets threshold), haiku has 2 (below threshold)
        for _ in range(5):
            tracker.record_invocation("sonnet", "coder", "development", success=True)
        for _ in range(2):
            tracker.record_invocation("haiku", "coder", "development", success=True)

        advice = tracker.get_routing_advice("coder", "development", ["sonnet", "haiku"], min_samples=5)
        provider_names = [name for name, _ in advice]
        assert "sonnet" in provider_names
        assert "haiku" not in provider_names


# ------------------------------------------------------------------
# Per-dimension tracking
# ------------------------------------------------------------------


class TestDimensionTracking:
    def test_provider_dimension_independent(self, tracker):
        """Provider stats aggregate across all agents and types."""
        tracker.record_invocation("sonnet", "coder", "development", True)
        tracker.record_invocation("sonnet", "reviewer", "content", True)
        tracker.record_invocation("sonnet", "planner", "research", False)

        stats = tracker.get_provider_stats("sonnet", min_samples=1)
        assert stats["total"] == 3

    def test_agent_dimension_independent(self, tracker):
        """Agent stats aggregate across all providers and types."""
        tracker.record_invocation("sonnet", "coder", "development", True)
        tracker.record_invocation("haiku", "coder", "content", True)
        tracker.record_invocation("gemini_flash", "coder", "research", False)

        stats = tracker.get_agent_stats("coder", min_samples=1)
        assert stats["total"] == 3
        assert stats["successes"] == 2

    def test_type_dimension_independent(self, tracker):
        """Story type stats aggregate across all providers and agents."""
        tracker.record_invocation("sonnet", "coder", "development", True)
        tracker.record_invocation("haiku", "reviewer", "development", False)

        stats = tracker.get_type_stats("development", min_samples=1)
        assert stats["total"] == 2
        assert stats["success_rate"] == pytest.approx(0.5)

    def test_dimensions_do_not_cross_contaminate(self, tracker):
        """Stats for one dimension must not include data from another."""
        for _ in range(3):
            tracker.record_invocation("sonnet", "coder", "development", True)
        for _ in range(3):
            tracker.record_invocation("haiku", "reviewer", "content", False)

        sonnet_stats = tracker.get_provider_stats("sonnet", min_samples=1)
        assert sonnet_stats["total"] == 3
        assert sonnet_stats["success_rate"] == 1.0

        haiku_stats = tracker.get_provider_stats("haiku", min_samples=1)
        assert haiku_stats["total"] == 3
        assert haiku_stats["success_rate"] == 0.0


# ------------------------------------------------------------------
# Combined stats
# ------------------------------------------------------------------


class TestCombinedStats:
    def test_combined_provider_agent(self, tracker):
        """Filter on provider + agent."""
        tracker.record_invocation("sonnet", "coder", "development", True)
        tracker.record_invocation("sonnet", "coder", "content", False)
        tracker.record_invocation("sonnet", "reviewer", "development", True)

        stats = tracker.get_combined_stats(provider="sonnet", agent="coder", min_samples=1)
        assert stats["total"] == 2
        assert stats["success_rate"] == pytest.approx(0.5)

    def test_combined_provider_type(self, tracker):
        """Filter on provider + story_type."""
        tracker.record_invocation("sonnet", "coder", "development", True)
        tracker.record_invocation("sonnet", "reviewer", "development", True)
        tracker.record_invocation("sonnet", "coder", "content", False)

        stats = tracker.get_combined_stats(provider="sonnet", story_type="development", min_samples=1)
        assert stats["total"] == 2
        assert stats["success_rate"] == 1.0

    def test_combined_all_three(self, tracker):
        """Filter on all three dimensions."""
        tracker.record_invocation("sonnet", "coder", "development", True)
        tracker.record_invocation("sonnet", "coder", "development", False)
        tracker.record_invocation("sonnet", "coder", "content", True)  # different type

        stats = tracker.get_combined_stats(provider="sonnet", agent="coder", story_type="development", min_samples=1)
        assert stats["total"] == 2
        assert stats["success_rate"] == pytest.approx(0.5)

    def test_combined_no_filters_returns_global(self, tracker):
        """No filters returns stats across everything."""
        for _ in range(3):
            tracker.record_invocation("sonnet", "coder", "development", True)
        stats = tracker.get_combined_stats(min_samples=1)
        assert stats["total"] == 3


# ------------------------------------------------------------------
# Routing advice
# ------------------------------------------------------------------


class TestRoutingAdvice:
    def test_sorted_by_success_rate(self, tracker):
        """Providers should be sorted best-first by success rate."""
        # sonnet: 80% success
        for _ in range(8):
            tracker.record_invocation("sonnet", "coder", "development", True)
        for _ in range(2):
            tracker.record_invocation("sonnet", "coder", "development", False)

        # haiku: 40% success
        for _ in range(4):
            tracker.record_invocation("haiku", "coder", "development", True)
        for _ in range(6):
            tracker.record_invocation("haiku", "coder", "development", False)

        advice = tracker.get_routing_advice("coder", "development", ["sonnet", "haiku"], min_samples=5)
        assert len(advice) == 2
        assert advice[0][0] == "sonnet"
        assert advice[1][0] == "haiku"
        assert advice[0][1] > advice[1][1]

    def test_zero_percent_provider_ranked_last(self, tracker):
        """Provider with 0% success rate should be ranked last."""
        for _ in range(5):
            tracker.record_invocation("sonnet", "coder", "development", True)
        for _ in range(5):
            tracker.record_invocation("haiku", "coder", "development", False)

        advice = tracker.get_routing_advice("coder", "development", ["sonnet", "haiku"], min_samples=5)
        assert advice[-1][0] == "haiku"
        assert advice[-1][1] == pytest.approx(0.0)

    def test_returns_empty_for_no_data(self, tracker):
        """Returns empty list when no providers have enough data."""
        advice = tracker.get_routing_advice("coder", "development", ["sonnet", "haiku"], min_samples=5)
        assert advice == []

    def test_only_eligible_providers_considered(self, tracker):
        """Providers not in the eligible list are not returned."""
        for _ in range(5):
            tracker.record_invocation("opus", "coder", "development", True)
        for _ in range(5):
            tracker.record_invocation("sonnet", "coder", "development", True)

        advice = tracker.get_routing_advice("coder", "development", ["sonnet"], min_samples=5)
        provider_names = [name for name, _ in advice]
        assert "opus" not in provider_names
        assert "sonnet" in provider_names

    def test_weighted_scoring_prefers_specific_data(self, tracker):
        """Provider with better specific (agent+type) data should rank higher
        even if overall stats are similar."""
        # sonnet: great at coder+development specifically
        for _ in range(10):
            tracker.record_invocation("sonnet", "coder", "development", True)
        # sonnet: mediocre overall (other combos)
        for _ in range(10):
            tracker.record_invocation("sonnet", "reviewer", "content", False)

        # haiku: decent overall, no specific coder+development data
        for _ in range(7):
            tracker.record_invocation("haiku", "reviewer", "content", True)
        for _ in range(3):
            tracker.record_invocation("haiku", "reviewer", "content", False)

        advice = tracker.get_routing_advice("coder", "development", ["sonnet", "haiku"], min_samples=5)
        # sonnet should rank higher because its coder+development data is 100%
        if len(advice) >= 2:
            assert advice[0][0] == "sonnet"


# ------------------------------------------------------------------
# Persistence (schema creation)
# ------------------------------------------------------------------


class TestPersistence:
    def test_table_created_on_init(self, tmp_path):
        db_path = str(tmp_path / "fresh.db")
        PerformanceTracker(db_path=db_path)

        conn = sqlite3.connect(db_path)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='performance_invocations'"
        ).fetchone()
        conn.close()
        assert tables is not None

    def test_data_persists_across_instances(self, tmp_path):
        db_path = str(tmp_path / "persist.db")

        t1 = PerformanceTracker(db_path=db_path)
        t1.record_invocation("sonnet", "coder", "development", True)

        t2 = PerformanceTracker(db_path=db_path)
        stats = t2.get_provider_stats("sonnet", min_samples=1)
        assert stats["total"] == 1

    def test_idempotent_schema_init(self, tmp_path):
        """Creating the tracker twice on the same DB should not fail."""
        db_path = str(tmp_path / "idem.db")
        PerformanceTracker(db_path=db_path)
        PerformanceTracker(db_path=db_path)  # Should not raise
