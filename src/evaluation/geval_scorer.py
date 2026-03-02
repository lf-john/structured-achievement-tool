"""
G-Eval Idle-Time Scorer — Deferred LLM output quality evaluation.

Scores LLM invocation responses during idle time using Nemotron (local, free).
Three dimensions: completeness, correctness, format_compliance (each 1-5).

Flow:
1. COLLECT: After each LLM invocation, log_event() saves response data to events.jsonl
2. SCORE: During monitor idle time, score_pending_invocations() evaluates unscored responses
3. AGGREGATE: Scores stored in provider_performance table (sqlite)
4. ACT: Daily digest surfaces providers with avg score <= 2

This is A/B testing your LLM providers with deferred evaluation. The idle-time
constraint means it costs nothing during active work.
"""

import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    ".memory", "geval_scores.db"
)

EVENTS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    ".memory", "events.jsonl"
)

# Scoring prompt sent to Nemotron
SCORING_PROMPT = """You are a quality evaluator. Score this LLM response on 3 dimensions (1-5 each):

1. **completeness** — Did it address all aspects of the task? (1=missed most, 5=addressed all)
2. **correctness** — Is the output factually/logically correct? (1=major errors, 5=fully correct)
3. **format_compliance** — Does it follow the expected format (JSON, markdown, etc.)? (1=wrong format, 5=perfect format)

## Task Context
Agent type: {agent_type}
Phase: {phase}

## Response to evaluate (first 2000 chars):
{response_preview}

## Output
Respond with ONLY a JSON object:
{{"completeness": N, "correctness": N, "format_compliance": N, "notes": "brief explanation"}}
"""

BATCH_SIZE = 5  # Score this many invocations per idle cycle


@dataclass
class InvocationScore:
    """Quality score for a single LLM invocation."""
    provider: str
    agent_type: str
    completeness: int
    correctness: int
    format_compliance: int
    notes: str = ""
    timestamp: str = ""


def _init_db(db_path: str):
    """Initialize the G-Eval scores database."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS geval_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                provider TEXT NOT NULL,
                agent_type TEXT NOT NULL,
                completeness INTEGER NOT NULL,
                correctness INTEGER NOT NULL,
                format_compliance INTEGER NOT NULL,
                notes TEXT,
                event_ts TEXT UNIQUE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scoring_progress (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        # Add agent_confidence and template_version columns (self-assessment tracking)
        for col, col_type in [
            ("agent_confidence", "INTEGER"),
            ("template_version", "TEXT"),
        ]:
            try:
                conn.execute(f"ALTER TABLE geval_scores ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass  # Column already exists


def _get_last_scored_offset(db_path: str) -> int:
    """Get the byte offset of the last scored event in events.jsonl."""
    try:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT value FROM scoring_progress WHERE key = 'last_offset'"
            ).fetchone()
            return int(row[0]) if row else 0
    except Exception:
        return 0


def _set_last_scored_offset(db_path: str, offset: int):
    """Save the byte offset of the last scored event."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO scoring_progress (key, value) VALUES ('last_offset', ?)",
            (str(offset),)
        )


def _get_pending_invocations(
    events_file: str,
    db_path: str,
    batch_size: int = BATCH_SIZE,
) -> List[dict]:
    """Read unscored LLM invocations from events.jsonl."""
    if not os.path.exists(events_file):
        return []

    offset = _get_last_scored_offset(db_path)
    pending = []

    try:
        with open(events_file, "r") as f:
            f.seek(offset)
            for line in f:
                try:
                    event = json.loads(line.strip())
                    if event.get("event_type") == "llm_invocation":
                        pending.append(event)
                        if len(pending) >= batch_size:
                            break
                except json.JSONDecodeError:
                    continue
            new_offset = f.tell()
    except Exception as e:
        logger.warning(f"Error reading events for scoring: {e}")
        return []

    _set_last_scored_offset(db_path, new_offset)
    return pending


def score_pending_invocations(
    db_path: str = DEFAULT_DB_PATH,
    events_file: str = EVENTS_FILE,
    batch_size: int = BATCH_SIZE,
) -> int:
    """Score pending LLM invocations using Nemotron.

    Called by the monitor during idle time. Returns the number of invocations scored.
    """
    _init_db(db_path)
    pending = _get_pending_invocations(events_file, db_path, batch_size)

    if not pending:
        return 0

    scored = 0
    for event in pending:
        try:
            data = event.get("data", {})
            provider = data.get("provider", "unknown")
            agent_type = data.get("agent_type", "unknown")
            response_preview = data.get("output_preview", "")[:2000]
            phase = data.get("phase", "unknown")

            if not response_preview:
                continue

            # Score using Nemotron (local, free)
            score = _score_with_nemotron(agent_type, phase, response_preview)
            if score:
                # Pass agent self-assessment and template version for calibration tracking
                agent_confidence = data.get("agent_confidence")
                if agent_confidence is not None:
                    try:
                        agent_confidence = max(1, min(5, int(agent_confidence)))
                    except (ValueError, TypeError):
                        agent_confidence = None
                _save_score(
                    db_path, score, event.get("ts", ""),
                    agent_confidence=agent_confidence,
                    template_version=data.get("template_version"),
                )
                scored += 1

        except Exception as e:
            logger.debug(f"Failed to score invocation: {e}")

    logger.info(f"G-Eval: scored {scored}/{len(pending)} invocations")
    return scored


def _score_with_nemotron(agent_type: str, phase: str, response_preview: str) -> Optional[InvocationScore]:
    """Call Nemotron to score a response. Returns None on failure."""
    import subprocess

    prompt = SCORING_PROMPT.format(
        agent_type=agent_type,
        phase=phase,
        response_preview=response_preview,
    )

    try:
        result = subprocess.run(
            ["ollama", "run", "nemotron-mini"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            return None

        # Parse JSON from output
        output = result.stdout.strip()
        # Find JSON in output
        start = output.find("{")
        end = output.rfind("}") + 1
        if start == -1 or end == 0:
            return None

        parsed = json.loads(output[start:end])
        return InvocationScore(
            provider="",  # filled by caller
            agent_type=agent_type,
            completeness=max(1, min(5, int(parsed.get("completeness", 3)))),
            correctness=max(1, min(5, int(parsed.get("correctness", 3)))),
            format_compliance=max(1, min(5, int(parsed.get("format_compliance", 3)))),
            notes=parsed.get("notes", "")[:200],
        )
    except Exception as e:
        logger.debug(f"Nemotron scoring failed: {e}")
        return None


def _save_score(
    db_path: str,
    score: InvocationScore,
    event_ts: str,
    agent_confidence: Optional[int] = None,
    template_version: Optional[str] = None,
):
    """Save a score to the database."""
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO geval_scores "
                "(timestamp, provider, agent_type, completeness, correctness, "
                "format_compliance, notes, event_ts, agent_confidence, template_version) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    datetime.now().isoformat(),
                    score.provider,
                    score.agent_type,
                    score.completeness,
                    score.correctness,
                    score.format_compliance,
                    score.notes,
                    event_ts,
                    agent_confidence,
                    template_version,
                )
            )
    except Exception as e:
        logger.warning(f"Failed to save G-Eval score: {e}")


def get_provider_performance(db_path: str = DEFAULT_DB_PATH) -> Dict[str, dict]:
    """Get aggregated performance scores by provider and agent type.

    Returns: {provider: {agent_type: {avg_score, sample_count, low_scores, score_distribution}}}
    score_distribution is a dict of {dimension: {score: count}} for scores 1-5.
    """
    _init_db(db_path)
    results = {}
    try:
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute("""
                SELECT provider, agent_type,
                       AVG(completeness + correctness + format_compliance) / 3.0 as avg_score,
                       COUNT(*) as sample_count,
                       SUM(CASE WHEN completeness <= 2 OR correctness <= 2 OR format_compliance <= 2 THEN 1 ELSE 0 END) as low_scores
                FROM geval_scores
                GROUP BY provider, agent_type
            """).fetchall()
            for row in rows:
                provider = row[0]
                if provider not in results:
                    results[provider] = {}
                results[provider][row[1]] = {
                    "avg_score": round(row[2], 1),
                    "sample_count": row[3],
                    "low_scores": row[4],
                }

            # For providers with any score < 2, get per-score distribution
            for provider in results:
                for agent_type, scores in results[provider].items():
                    if scores["low_scores"] > 0:
                        dist = _get_score_distribution(conn, provider, agent_type)
                        scores["score_distribution"] = dist

    except Exception as e:
        logger.warning(f"Failed to get provider performance: {e}")
    return results


def _get_score_distribution(conn, provider: str, agent_type: str) -> Dict[str, Dict[int, int]]:
    """Get per-dimension score counts for a provider/agent_type pair."""
    dist = {"completeness": {}, "correctness": {}, "format_compliance": {}}
    for dim in dist:
        rows = conn.execute(
            f"SELECT {dim}, COUNT(*) FROM geval_scores "
            f"WHERE provider = ? AND agent_type = ? GROUP BY {dim}",
            (provider, agent_type),
        ).fetchall()
        for score_val, count in rows:
            dist[dim][score_val] = count
    return dist


def get_calibration_report(db_path: str = DEFAULT_DB_PATH) -> List[dict]:
    """Get agent self-assessment calibration data.

    Compares agent confidence (1-5) with G-Eval scores to measure how
    accurate agents are at self-scoring. Returns per-provider/agent stats.

    Positive delta = agent overestimates quality (overconfident).
    Negative delta = agent underestimates quality (underconfident).
    """
    _init_db(db_path)
    results = []
    try:
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute("""
                SELECT provider, agent_type,
                       COUNT(*) as sample_count,
                       AVG(agent_confidence) as avg_confidence,
                       AVG((completeness + correctness + format_compliance) / 3.0) as avg_geval,
                       AVG(agent_confidence - (completeness + correctness + format_compliance) / 3.0) as avg_delta
                FROM geval_scores
                WHERE agent_confidence IS NOT NULL
                GROUP BY provider, agent_type
                ORDER BY ABS(AVG(agent_confidence - (completeness + correctness + format_compliance) / 3.0)) DESC
            """).fetchall()
            for row in rows:
                results.append({
                    "provider": row[0],
                    "agent_type": row[1],
                    "sample_count": row[2],
                    "avg_confidence": round(row[3], 1),
                    "avg_geval": round(row[4], 1),
                    "avg_delta": round(row[5], 2),
                })
    except Exception as e:
        logger.warning(f"Failed to get calibration report: {e}")
    return results


def get_low_scoring_details(db_path: str = DEFAULT_DB_PATH) -> List[dict]:
    """Get details of invocations where any dimension scored <= 2.

    Used for the daily digest to surface quality issues.
    """
    _init_db(db_path)
    results = []
    try:
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute("""
                SELECT timestamp, provider, agent_type,
                       completeness, correctness, format_compliance, notes
                FROM geval_scores
                WHERE completeness <= 2 OR correctness <= 2 OR format_compliance <= 2
                ORDER BY timestamp DESC
                LIMIT 50
            """).fetchall()
            for row in rows:
                results.append({
                    "timestamp": row[0],
                    "provider": row[1],
                    "agent_type": row[2],
                    "completeness": row[3],
                    "correctness": row[4],
                    "format_compliance": row[5],
                    "notes": row[6],
                })
    except Exception as e:
        logger.warning(f"Failed to get low scoring details: {e}")
    return results
