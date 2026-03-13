"""
Historical Performance Tracker — Learn from past LLM invocation outcomes.

Tracks three independent dimensions (provider, agent, story_type) and assembles
combinations on query.  Used by the routing engine as a tie-breaker when
multiple providers are equally eligible.

Data is persisted in a dedicated ``performance_invocations`` table inside the
SAT SQLite database so it survives daemon restarts.
"""

import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

_PERF_SCHEMA = """
CREATE TABLE IF NOT EXISTS performance_invocations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    agent TEXT NOT NULL,
    story_type TEXT NOT NULL,
    success INTEGER NOT NULL,
    quality_score REAL,
    tokens INTEGER DEFAULT 0,
    duration_seconds REAL DEFAULT 0,
    timestamp TEXT NOT NULL DEFAULT (datetime('now','utc'))
);

CREATE INDEX IF NOT EXISTS idx_perf_provider ON performance_invocations(provider);
CREATE INDEX IF NOT EXISTS idx_perf_agent ON performance_invocations(agent);
CREATE INDEX IF NOT EXISTS idx_perf_story_type ON performance_invocations(story_type);
CREATE INDEX IF NOT EXISTS idx_perf_timestamp ON performance_invocations(timestamp);
"""


class PerformanceTracker:
    """Track and query historical LLM invocation performance.

    Each invocation is recorded with its three key dimensions:
    - **provider** (e.g. ``sonnet``, ``gemini_flash``)
    - **agent** (e.g. ``coder``, ``reviewer``)
    - **story_type** (e.g. ``development``, ``content``)

    Queries can filter on any single dimension or any combination of them.
    """

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = os.path.join(
                os.path.expanduser("~/projects/structured-achievement-tool"),
                ".memory",
                "sat.db",
            )
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._init_schema()

    def _init_schema(self):
        with self._connect() as conn:
            conn.executescript(_PERF_SCHEMA)

    @contextmanager
    def _connect(self):
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, timeout=30)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def close(self):
        """Close the cached database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_invocation(
        self,
        provider: str,
        agent: str,
        story_type: str,
        success: bool,
        quality_score: float | None = None,
        tokens: int = 0,
        duration_seconds: float = 0.0,
    ):
        """Record a single invocation result."""
        now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO performance_invocations "
                "(provider, agent, story_type, success, quality_score, tokens, "
                "duration_seconds, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (provider, agent, story_type, 1 if success else 0, quality_score, tokens, duration_seconds, now),
            )

    # ------------------------------------------------------------------
    # Single-dimension queries
    # ------------------------------------------------------------------

    def get_provider_stats(self, provider: str, min_samples: int = 5) -> dict:
        """Aggregated stats for a provider across all agents/types."""
        return self.get_combined_stats(provider=provider, min_samples=min_samples)

    def get_agent_stats(self, agent: str, min_samples: int = 5) -> dict:
        """Aggregated stats for an agent across all providers/types."""
        return self.get_combined_stats(agent=agent, min_samples=min_samples)

    def get_type_stats(self, story_type: str, min_samples: int = 5) -> dict:
        """Aggregated stats for a story type across all providers/agents."""
        return self.get_combined_stats(story_type=story_type, min_samples=min_samples)

    # ------------------------------------------------------------------
    # Combined query
    # ------------------------------------------------------------------

    def get_combined_stats(
        self,
        provider: str | None = None,
        agent: str | None = None,
        story_type: str | None = None,
        min_samples: int = 3,
    ) -> dict:
        """Get stats for any combination of dimensions.

        Returns a dict with: total, successes, failures, success_rate,
        avg_quality, avg_tokens, avg_duration.  Returns an empty dict if
        fewer than *min_samples* invocations match.
        """
        clauses: list[str] = []
        params: list = []
        if provider is not None:
            clauses.append("provider = ?")
            params.append(provider)
        if agent is not None:
            clauses.append("agent = ?")
            params.append(agent)
        if story_type is not None:
            clauses.append("story_type = ?")
            params.append(story_type)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        with self._connect() as conn:
            row = conn.execute(
                f"SELECT COUNT(*) as total, "
                f"SUM(success) as successes, "
                f"AVG(quality_score) as avg_quality, "
                f"AVG(tokens) as avg_tokens, "
                f"AVG(duration_seconds) as avg_duration "
                f"FROM performance_invocations {where}",
                params,
            ).fetchone()

        total = row["total"] or 0
        if total < min_samples:
            return {}

        successes = row["successes"] or 0
        return {
            "total": total,
            "successes": successes,
            "failures": total - successes,
            "success_rate": successes / total if total else 0.0,
            "avg_quality": row["avg_quality"],
            "avg_tokens": row["avg_tokens"],
            "avg_duration": row["avg_duration"],
        }

    # ------------------------------------------------------------------
    # Routing advice
    # ------------------------------------------------------------------

    def get_routing_advice(
        self,
        agent: str,
        story_type: str,
        eligible_providers: list[str],
        min_samples: int = 5,
    ) -> list[tuple[str, float]]:
        """Rank eligible providers by historical success rate.

        Tries the most specific combination first (provider + agent + story_type),
        then falls back to (provider + agent), then (provider + story_type),
        then provider-only.  Providers with fewer than *min_samples* invocations
        at ANY granularity are excluded from the ranking.

        Returns ``[(provider_name, score)]`` sorted best-first.
        """
        scored: list[tuple[str, float]] = []

        for prov in eligible_providers:
            score = self._score_provider(prov, agent, story_type, min_samples)
            if score is not None:
                scored.append((prov, score))

        scored.sort(key=lambda x: -x[1])
        return scored

    def _score_provider(
        self,
        provider: str,
        agent: str,
        story_type: str,
        min_samples: int,
    ) -> float | None:
        """Compute a composite score for a provider given an agent+type context.

        Returns None if no dimension has enough samples.  Otherwise builds a
        weighted average from whichever granularities have enough data:
        - exact combo (provider+agent+type): weight 3
        - provider+agent: weight 2
        - provider+type: weight 2
        - provider overall: weight 1

        NOTE: Each call issues 4 separate get_combined_stats queries (one per
        granularity).  For N eligible providers this means 4*N queries per
        routing decision.  The table is small so this is fine for now, but if
        the invocation table grows large, refactor to a single query that
        fetches all four granularities at once (e.g. via UNION ALL or a
        grouped CTE).
        """
        combos = [
            ({"provider": provider, "agent": agent, "story_type": story_type}, 3),
            ({"provider": provider, "agent": agent}, 2),
            ({"provider": provider, "story_type": story_type}, 2),
            ({"provider": provider}, 1),
        ]

        weighted_sum = 0.0
        total_weight = 0

        for kwargs, weight in combos:
            stats = self.get_combined_stats(**kwargs, min_samples=min_samples)
            if stats:
                weighted_sum += stats["success_rate"] * weight
                total_weight += weight

        if total_weight == 0:
            return None

        return weighted_sum / total_weight
