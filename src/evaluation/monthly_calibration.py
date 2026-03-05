"""
Monthly Calibration Report — Recommendations-only analysis of SAT system performance.

Produces a markdown report with:
- Cost report: total spend by provider, cost per invocation, cost per successful story
- Reliability report: success rate by provider x agent type, failure categories
- Quality report: G-Eval scores by provider x agent type
- Routing recommendations: complexity adjustment suggestions (not applied)
- Budget projection: monthly cost estimate at current rates

Data sources (all optional — gracefully skipped if missing):
- .memory/llm_costs.db     (llm_costs table)
- .memory/audit_journal.jsonl (JSONL audit entries)
- .memory/geval_scores.db  (geval_scores table)
- .memory/sat.db            (events table)

Runs on the 1st of each month via systemd timer.
Output: .memory/calibration/YYYY-MM.md + ntfy notification.
"""

import json
import logging
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
MEMORY_DIR = PROJECT_DIR / ".memory"
CALIBRATION_DIR = MEMORY_DIR / "calibration"
LOG_DIR = PROJECT_DIR / "logs"

LLM_COSTS_DB = MEMORY_DIR / "llm_costs.db"
GEVAL_SCORES_DB = MEMORY_DIR / "geval_scores.db"
SAT_DB = MEMORY_DIR / "sat.db"
AUDIT_JOURNAL = MEMORY_DIR / "audit_journal.jsonl"

NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "johnlane-claude-tasks")
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("sat.calibration")
logger.setLevel(logging.DEBUG)

_fh = logging.FileHandler(LOG_DIR / "monthly_calibration.log")
_fh.setLevel(logging.DEBUG)
_fh.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
))
logger.addHandler(_fh)

_sh = logging.StreamHandler(sys.stderr)
_sh.setLevel(logging.INFO)
_sh.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
logger.addHandler(_sh)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _period_bounds(reference: datetime | None = None) -> tuple[str, str, str]:
    """Return (label, start_iso, end_iso) for the preceding calendar month."""
    ref = reference or datetime.utcnow()
    first_of_this_month = ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = first_of_this_month  # exclusive upper bound
    start = (first_of_this_month - timedelta(days=1)).replace(day=1)
    label = start.strftime("%Y-%m")
    return label, start.isoformat(), end.isoformat()


def _safe_db_query(db_path: Path, sql: str, params: tuple = ()) -> list[tuple]:
    """Run a read-only query against a SQLite database. Returns [] on any error."""
    if not db_path.exists():
        logger.info("Database not found, skipping: %s", db_path)
        return []
    try:
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
            return [tuple(row) for row in rows]
    except Exception as exc:
        logger.warning("Query failed on %s: %s", db_path.name, exc)
        return []


def _safe_db_query_dicts(db_path: Path, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    """Like _safe_db_query but returns list of dicts."""
    if not db_path.exists():
        logger.info("Database not found, skipping: %s", db_path)
        return []
    try:
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]
    except Exception as exc:
        logger.warning("Query failed on %s: %s", db_path.name, exc)
        return []


def _read_audit_journal(start_iso: str, end_iso: str) -> list[dict[str, Any]]:
    """Read audit_journal.jsonl entries within the period."""
    if not AUDIT_JOURNAL.exists():
        logger.info("Audit journal not found, skipping: %s", AUDIT_JOURNAL)
        return []
    entries = []
    try:
        with open(AUDIT_JOURNAL) as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    logger.debug("Malformed JSON at audit_journal line %d", lineno)
                    continue
                ts = entry.get("timestamp", "")
                if start_iso <= ts < end_iso:
                    entries.append(entry)
    except Exception as exc:
        logger.warning("Error reading audit journal: %s", exc)
    return entries


def _fmt_usd(val: float) -> str:
    """Format a USD amount."""
    if val < 0.01:
        return f"${val:.4f}"
    return f"${val:.2f}"


def _pct(num: int, denom: int) -> str:
    """Format a percentage safely."""
    if denom == 0:
        return "N/A"
    return f"{100.0 * num / denom:.1f}%"


def _send_ntfy(title: str, body: str, priority: str = "default"):
    """Send a notification via ntfy.sh."""
    url = f"{NTFY_SERVER}/{NTFY_TOPIC}"
    try:
        req = urllib.request.Request(url, data=body.encode("utf-8"), method="POST")
        req.add_header("Title", title)
        req.add_header("Priority", priority)
        req.add_header("Tags", "chart_with_upwards_trend,clipboard")
        with urllib.request.urlopen(req, timeout=15) as resp:
            logger.info("Ntfy notification sent (%d)", resp.status)
    except (urllib.error.URLError, OSError) as exc:
        logger.warning("Failed to send ntfy notification: %s", exc)


# ---------------------------------------------------------------------------
# Report sections
# ---------------------------------------------------------------------------

@dataclass
class ReportData:
    """Aggregated data used across report sections."""
    label: str = ""
    start_iso: str = ""
    end_iso: str = ""
    # Cost data
    cost_rows: list[dict[str, Any]] = field(default_factory=list)
    # Events data (from sat.db)
    event_rows: list[dict[str, Any]] = field(default_factory=list)
    # Audit journal entries
    audit_entries: list[dict[str, Any]] = field(default_factory=list)
    # G-Eval scores
    geval_rows: list[dict[str, Any]] = field(default_factory=list)


def _gather_data(label: str, start_iso: str, end_iso: str) -> ReportData:
    """Collect all data for the reporting period."""
    rd = ReportData(label=label, start_iso=start_iso, end_iso=end_iso)

    # LLM costs
    rd.cost_rows = _safe_db_query_dicts(
        LLM_COSTS_DB,
        "SELECT model_name, prompt_tokens, completion_tokens, estimated_cost, timestamp "
        "FROM llm_costs WHERE timestamp >= ? AND timestamp < ?",
        (start_iso, end_iso),
    )
    logger.info("Cost rows for period: %d", len(rd.cost_rows))

    # Events from sat.db
    rd.event_rows = _safe_db_query_dicts(
        SAT_DB,
        "SELECT story_id, task_id, event_type, phase, provider, detail, "
        "tokens_used, cost_estimate, timestamp "
        "FROM events WHERE timestamp >= ? AND timestamp < ?",
        (start_iso, end_iso),
    )
    logger.info("Event rows for period: %d", len(rd.event_rows))

    # Audit journal
    rd.audit_entries = _read_audit_journal(start_iso, end_iso)
    logger.info("Audit journal entries for period: %d", len(rd.audit_entries))

    # G-Eval scores
    rd.geval_rows = _safe_db_query_dicts(
        GEVAL_SCORES_DB,
        "SELECT provider, agent_type, completeness, correctness, format_compliance, "
        "agent_confidence, template_version, timestamp "
        "FROM geval_scores WHERE timestamp >= ? AND timestamp < ?",
        (start_iso, end_iso),
    )
    logger.info("G-Eval score rows for period: %d", len(rd.geval_rows))

    return rd


def _section_cost(rd: ReportData) -> str:
    """Generate the Cost Report section."""
    lines = ["## Cost Report", ""]

    if not rd.cost_rows and not rd.event_rows:
        lines.append("_No cost data recorded for this period._")
        return "\n".join(lines)

    # Aggregate by provider/model from llm_costs.db
    by_model: dict[str, dict[str, float]] = defaultdict(lambda: {
        "cost": 0.0, "prompt_tokens": 0, "completion_tokens": 0, "invocations": 0
    })
    for row in rd.cost_rows:
        model = row["model_name"]
        by_model[model]["cost"] += row["estimated_cost"]
        by_model[model]["prompt_tokens"] += row["prompt_tokens"]
        by_model[model]["completion_tokens"] += row["completion_tokens"]
        by_model[model]["invocations"] += 1

    # Also aggregate cost_estimate from sat.db events (may overlap, noted in report)
    events_cost_by_provider: dict[str, float] = defaultdict(float)
    events_invocations_by_provider: dict[str, int] = defaultdict(int)
    for ev in rd.event_rows:
        if ev.get("cost_estimate") and ev.get("provider"):
            events_cost_by_provider[ev["provider"]] += ev["cost_estimate"]
            events_invocations_by_provider[ev["provider"]] += 1

    total_cost = sum(m["cost"] for m in by_model.values())
    total_invocations = sum(m["invocations"] for m in by_model.values())

    # Successful stories from audit journal
    successful_stories = sum(1 for e in rd.audit_entries if e.get("success"))
    len(rd.audit_entries)

    lines.append(f"**Total spend (llm_costs.db):** {_fmt_usd(total_cost)}")
    lines.append(f"**Total invocations:** {total_invocations}")
    if successful_stories > 0:
        lines.append(f"**Cost per successful story:** {_fmt_usd(total_cost / successful_stories)}")
    if total_invocations > 0:
        lines.append(f"**Cost per invocation:** {_fmt_usd(total_cost / total_invocations)}")
    lines.append("")

    # Table: by model
    lines.append("### Spend by Model")
    lines.append("")
    lines.append("| Model | Invocations | Prompt Tokens | Completion Tokens | Cost |")
    lines.append("|-------|------------|---------------|-------------------|------|")
    for model in sorted(by_model, key=lambda m: by_model[m]["cost"], reverse=True):
        m = by_model[model]
        lines.append(
            f"| {model} | {m['invocations']} | {m['prompt_tokens']:,} "
            f"| {m['completion_tokens']:,} | {_fmt_usd(m['cost'])} |"
        )
    lines.append("")

    # If events table has additional provider-level cost data, show it
    if events_cost_by_provider:
        lines.append("### Spend by Provider (sat.db events)")
        lines.append("")
        lines.append("| Provider | Invocations | Estimated Cost |")
        lines.append("|----------|------------|----------------|")
        for prov in sorted(events_cost_by_provider, key=lambda p: events_cost_by_provider[p], reverse=True):
            lines.append(
                f"| {prov} | {events_invocations_by_provider[prov]} "
                f"| {_fmt_usd(events_cost_by_provider[prov])} |"
            )
        lines.append("")

    return "\n".join(lines)


def _section_reliability(rd: ReportData) -> str:
    """Generate the Reliability Report section."""
    lines = ["## Reliability Report", ""]

    if not rd.audit_entries:
        lines.append("_No audit journal entries for this period._")
        return "\n".join(lines)

    total = len(rd.audit_entries)
    successes = sum(1 for e in rd.audit_entries if e.get("success"))
    failures = total - successes

    lines.append(f"**Total story executions:** {total}")
    lines.append(f"**Successes:** {successes} ({_pct(successes, total)})")
    lines.append(f"**Failures:** {failures} ({_pct(failures, total)})")
    lines.append("")

    # Success rate by task file (proxy for agent type / domain)
    by_task: dict[str, dict[str, int]] = defaultdict(lambda: {"success": 0, "total": 0})
    for e in rd.audit_entries:
        # Use the parent directory name as the task domain
        tf = e.get("task_file", "unknown")
        domain = Path(tf).parent.name if tf != "unknown" else "unknown"
        by_task[domain]["total"] += 1
        if e.get("success"):
            by_task[domain]["success"] += 1

    lines.append("### Success Rate by Task Domain")
    lines.append("")
    lines.append("| Domain | Total | Successes | Rate |")
    lines.append("|--------|-------|-----------|------|")
    for domain in sorted(by_task, key=lambda d: by_task[d]["total"], reverse=True):
        d = by_task[domain]
        lines.append(f"| {domain} | {d['total']} | {d['success']} | {_pct(d['success'], d['total'])} |")
    lines.append("")

    # Failure categories
    failure_entries = [e for e in rd.audit_entries if not e.get("success")]
    if failure_entries:
        error_cats: dict[str, int] = defaultdict(int)
        for e in failure_entries:
            summary = e.get("error_summary") or "unknown"
            # Normalize to first 80 chars for grouping
            key = summary[:80].strip()
            error_cats[key] += 1

        lines.append("### Failure Categories")
        lines.append("")
        lines.append("| Error Summary | Count |")
        lines.append("|---------------|-------|")
        for err, cnt in sorted(error_cats.items(), key=lambda x: x[1], reverse=True)[:15]:
            lines.append(f"| {err} | {cnt} |")
        lines.append("")

    # Provider-level reliability from sat.db events
    provider_outcomes: dict[str, dict[str, int]] = defaultdict(lambda: {"success": 0, "fail": 0})
    for ev in rd.event_rows:
        prov = ev.get("provider")
        etype = ev.get("event_type", "")
        if not prov:
            continue
        if "success" in etype.lower() or "complete" in etype.lower():
            provider_outcomes[prov]["success"] += 1
        elif "fail" in etype.lower() or "error" in etype.lower():
            provider_outcomes[prov]["fail"] += 1

    if provider_outcomes:
        lines.append("### Provider Reliability (sat.db events)")
        lines.append("")
        lines.append("| Provider | Successes | Failures | Rate |")
        lines.append("|----------|-----------|----------|------|")
        for prov in sorted(provider_outcomes):
            p = provider_outcomes[prov]
            tot = p["success"] + p["fail"]
            lines.append(
                f"| {prov} | {p['success']} | {p['fail']} | {_pct(p['success'], tot)} |"
            )
        lines.append("")

    return "\n".join(lines)


def _section_quality(rd: ReportData) -> str:
    """Generate the Quality Report section (G-Eval scores)."""
    lines = ["## Quality Report (G-Eval)", ""]

    if not rd.geval_rows:
        lines.append("_No G-Eval scores recorded for this period._")
        return "\n".join(lines)

    # Aggregate by provider x agent_type
    key_scores: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rd.geval_rows:
        key = (row.get("provider", "unknown"), row.get("agent_type", "unknown"))
        key_scores[key].append(row)

    lines.append("| Provider | Agent Type | N | Completeness | Correctness | Format | Confidence |")
    lines.append("|----------|-----------|---|-------------|-------------|--------|------------|")

    for (prov, atype) in sorted(key_scores):
        scores = key_scores[(prov, atype)]
        n = len(scores)
        avg_comp = sum(s.get("completeness", 0) for s in scores) / n
        avg_corr = sum(s.get("correctness", 0) for s in scores) / n
        avg_fmt = sum(s.get("format_compliance", 0) for s in scores) / n
        conf_vals = [s.get("agent_confidence") for s in scores if s.get("agent_confidence") is not None]
        avg_conf = f"{sum(conf_vals) / len(conf_vals):.1f}" if conf_vals else "N/A"
        lines.append(
            f"| {prov} | {atype} | {n} | {avg_comp:.2f} | {avg_corr:.2f} "
            f"| {avg_fmt:.2f} | {avg_conf} |"
        )
    lines.append("")

    # Flag low-quality combinations
    alerts = []
    for (prov, atype), scores in key_scores.items():
        n = len(scores)
        if n < 3:
            continue
        avg_corr = sum(s.get("correctness", 0) for s in scores) / n
        if avg_corr <= 2.5:
            alerts.append(f"- **{prov} / {atype}**: avg correctness {avg_corr:.2f} (below threshold)")

    if alerts:
        lines.append("### Quality Alerts")
        lines.append("")
        lines.extend(alerts)
        lines.append("")

    return "\n".join(lines)


def _section_routing_recommendations(rd: ReportData) -> str:
    """Generate routing/complexity adjustment recommendations."""
    lines = ["## Routing Recommendations", ""]
    lines.append("_These are suggestions only -- no automatic adjustments are made._")
    lines.append("")

    recommendations = []

    # Analyze cost efficiency: flag models where cost/invocation is high but quality is low
    model_costs: dict[str, dict[str, float]] = defaultdict(lambda: {"cost": 0.0, "invocations": 0})
    for row in rd.cost_rows:
        m = row["model_name"]
        model_costs[m]["cost"] += row["estimated_cost"]
        model_costs[m]["invocations"] += 1

    for model, data in model_costs.items():
        if data["invocations"] == 0:
            continue
        cpi = data["cost"] / data["invocations"]
        # Expensive invocations: flag if cost > $0.10 per call
        if cpi > 0.10:
            recommendations.append(
                f"- **{model}**: cost per invocation is {_fmt_usd(cpi)} "
                f"({data['invocations']} calls). Consider routing simpler tasks to a cheaper model."
            )

    # Check if local models are underutilized
    local_models = [m for m in model_costs if any(
        tag in m.lower() for tag in ["qwen", "deepseek", "nemotron", "llama", "mistral"]
    )]
    [m for m in model_costs if m not in local_models]
    total_inv = sum(model_costs[m]["invocations"] for m in model_costs)
    local_inv = sum(model_costs[m]["invocations"] for m in local_models)

    if total_inv > 0 and local_inv / total_inv < 0.2 and local_models:
        recommendations.append(
            f"- Local models handled only {_pct(local_inv, total_inv)} of invocations. "
            "Consider routing more classification and formatting tasks to local models."
        )

    # Reliability-based: suggest steering away from high-failure providers
    provider_fail: dict[str, dict[str, int]] = defaultdict(lambda: {"success": 0, "fail": 0})
    for e in rd.audit_entries:
        # Try to extract provider from events
        if e.get("success"):
            provider_fail["all"]["success"] += 1
        else:
            provider_fail["all"]["fail"] += 1

    for ev in rd.event_rows:
        prov = ev.get("provider")
        if not prov:
            continue
        etype = ev.get("event_type", "")
        if "fail" in etype.lower() or "error" in etype.lower():
            provider_fail[prov]["fail"] += 1
        elif "success" in etype.lower() or "complete" in etype.lower():
            provider_fail[prov]["success"] += 1

    for prov, counts in provider_fail.items():
        if prov == "all":
            continue
        total = counts["success"] + counts["fail"]
        if total >= 5 and counts["fail"] / total > 0.3:
            recommendations.append(
                f"- **{prov}**: failure rate is {_pct(counts['fail'], total)} "
                f"({counts['fail']}/{total}). Consider reducing complexity tier or "
                "adding retry logic for this provider."
            )

    # G-Eval based: suggest complexity reduction for low-scoring combos
    key_scores: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rd.geval_rows:
        key = (row.get("provider", "unknown"), row.get("agent_type", "unknown"))
        key_scores[key].append(row)

    for (prov, atype), scores in key_scores.items():
        n = len(scores)
        if n < 3:
            continue
        avg_all = sum(
            s.get("completeness", 0) + s.get("correctness", 0) + s.get("format_compliance", 0)
            for s in scores
        ) / (n * 3)
        if avg_all <= 2.5:
            recommendations.append(
                f"- **{prov} / {atype}**: average G-Eval score is {avg_all:.2f}/5. "
                "Consider increasing complexity tier to use a more capable model for this agent."
            )

    if not recommendations:
        lines.append("No specific routing changes recommended at this time. "
                     "Current configuration appears reasonable based on available data.")
    else:
        lines.extend(recommendations)

    lines.append("")
    return "\n".join(lines)


def _section_budget_projection(rd: ReportData) -> str:
    """Generate a budget projection for the next month."""
    lines = ["## Budget Projection", ""]

    total_cost = sum(row["estimated_cost"] for row in rd.cost_rows)
    total_invocations = sum(1 for _ in rd.cost_rows)

    if total_invocations == 0:
        lines.append("_Insufficient data for budget projection._")
        return "\n".join(lines)

    # Calculate daily rate
    try:
        start_dt = datetime.fromisoformat(rd.start_iso)
        end_dt = datetime.fromisoformat(rd.end_iso)
        days_in_period = max((end_dt - start_dt).days, 1)
    except (ValueError, TypeError):
        days_in_period = 30

    daily_cost = total_cost / days_in_period
    daily_invocations = total_invocations / days_in_period

    projected_monthly = daily_cost * 30
    projected_invocations = daily_invocations * 30

    lines.append(f"**Period cost:** {_fmt_usd(total_cost)} over {days_in_period} days")
    lines.append(f"**Daily average:** {_fmt_usd(daily_cost)} ({daily_invocations:.1f} invocations/day)")
    lines.append(f"**30-day projection:** {_fmt_usd(projected_monthly)} (~{projected_invocations:.0f} invocations)")
    lines.append("")

    # Breakdown by model for projection
    model_daily: dict[str, float] = defaultdict(float)
    for row in rd.cost_rows:
        model_daily[row["model_name"]] += row["estimated_cost"] / days_in_period

    lines.append("### Projected Monthly Cost by Model")
    lines.append("")
    lines.append("| Model | Projected 30-day Cost |")
    lines.append("|-------|----------------------|")
    for model in sorted(model_daily, key=lambda m: model_daily[m], reverse=True):
        proj = model_daily[model] * 30
        if proj > 0.001:
            lines.append(f"| {model} | {_fmt_usd(proj)} |")
    lines.append("")

    # Budget alert thresholds
    if projected_monthly > 50:
        lines.append(f"> **Warning:** Projected monthly cost ({_fmt_usd(projected_monthly)}) exceeds $50. "
                     "Review expensive model usage above.")
        lines.append("")
    elif projected_monthly > 20:
        lines.append(f"> **Note:** Projected monthly cost ({_fmt_usd(projected_monthly)}) is moderate. "
                     "Monitor for growth trends.")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------

def generate_report(reference_date: datetime | None = None) -> tuple[str, str]:
    """
    Generate the full monthly calibration report.

    Args:
        reference_date: Date to use for determining the reporting period.
                       The report covers the calendar month before this date.
                       Defaults to now (so running on March 1 reports on February).

    Returns:
        (label, report_markdown) where label is "YYYY-MM" for the reported month.
    """
    label, start_iso, end_iso = _period_bounds(reference_date)
    logger.info("Generating calibration report for %s (%s to %s)", label, start_iso, end_iso)

    rd = _gather_data(label, start_iso, end_iso)

    sections = [
        f"# SAT Monthly Calibration Report: {label}",
        "",
        f"_Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC_",
        f"_Period: {start_iso[:10]} to {end_iso[:10]} (exclusive)_",
        "",
        "---",
        "",
        _section_cost(rd),
        "---",
        "",
        _section_reliability(rd),
        "---",
        "",
        _section_quality(rd),
        "---",
        "",
        _section_routing_recommendations(rd),
        "---",
        "",
        _section_budget_projection(rd),
        "---",
        "",
        "_This report contains recommendations only. No automatic adjustments have been made._",
        "",
    ]

    report = "\n".join(sections)
    return label, report


def _build_ntfy_summary(label: str, rd: ReportData) -> str:
    """Build a short summary for the ntfy notification."""
    total_cost = sum(row["estimated_cost"] for row in rd.cost_rows)
    total_invocations = len(rd.cost_rows)
    total_stories = len(rd.audit_entries)
    successes = sum(1 for e in rd.audit_entries if e.get("success"))
    geval_count = len(rd.geval_rows)

    parts = [
        f"Period: {label}",
        f"Cost: {_fmt_usd(total_cost)} ({total_invocations} invocations)",
        f"Stories: {successes}/{total_stories} succeeded",
    ]
    if geval_count > 0:
        parts.append(f"G-Eval scores: {geval_count} evaluations")
    parts.append(f"Report: .memory/calibration/{label}.md")
    return "\n".join(parts)


def main():
    """Entry point for the monthly calibration script."""
    logger.info("=== Monthly calibration run starting ===")

    try:
        label, report = generate_report()
    except Exception:
        logger.exception("Failed to generate calibration report")
        _send_ntfy(
            "SAT Calibration Failed",
            "Monthly calibration report generation failed. Check logs/monthly_calibration.log",
            priority="high",
        )
        sys.exit(1)

    # Write report
    CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)
    report_path = CALIBRATION_DIR / f"{label}.md"
    report_path.write_text(report, encoding="utf-8")
    logger.info("Report written to %s", report_path)

    # Re-gather data for notification summary (lightweight, uses cached period)
    label2, start_iso, end_iso = _period_bounds()
    rd = _gather_data(label2, start_iso, end_iso)
    summary = _build_ntfy_summary(label, rd)

    _send_ntfy(f"SAT Calibration Report: {label}", summary)

    logger.info("=== Monthly calibration run complete ===")


if __name__ == "__main__":
    main()
