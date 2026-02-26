#!/usr/bin/env python3
"""
Generates a structured Markdown audit report for the SAT system.

This script aggregates data from various system health checks and
formats it into a timestamped Markdown file.
"""

import os
import sys
from datetime import datetime

# Add src to path to allow importing from health_check
sys.path.append(os.path.join(os.path.dirname(__file__)))

from health_check import (
    check_service,
    check_ollama,
    check_gdrive,
    check_dashboard,
    scan_tasks,
    check_prometheus_targets
)

def format_status(status):
    """Formats a boolean or string status into color-coded Markdown."""
    if isinstance(status, str):
        if status.upper() == 'UP' or status.upper() == 'OK' or status.upper() == 'ACTIVE':
            return "**OK**"
        else:
            return f"~~{status.upper()}~~"
    if status:
        return "**OK**"
    return "~~FAIL~~"

def generate_report():
    """Gathers data and generates the Markdown report."""
    report_lines = []
    now = datetime.now()
    
    report_lines.append(f"# SAT System Audit Report")
    report_lines.append(f"")
    report_lines.append(f"**Timestamp:** `{now.isoformat()}`")
    report_lines.append(f"")
    report_lines.append(f"---")
    report_lines.append(f"")
    report_lines.append(f"## Core Services")
    report_lines.append(f"| Service | Status |")
    report_lines.append(f"|---|---|")
    report_lines.append(f"| SAT Daemon (`sat.service`) | {format_status(check_service('sat.service'))} |")
    report_lines.append(f"| SAT Monitor (`sat-monitor.service`) | {format_status(check_service('sat-monitor.service'))} |")
    report_lines.append(f"| Ollama | {format_status(check_ollama())} |")
    report_lines.append(f"| SAT Dashboard | {format_status(check_dashboard())} |")
    report_lines.append(f"")
    
    report_lines.append(f"## External Dependencies")
    report_lines.append(f"| Dependency | Status |")
    report_lines.append(f"|---|---|")
    report_lines.append(f"| Google Drive Mount | {format_status(check_gdrive())} |")
    report_lines.append(f"")
    
    report_lines.append(f"## Task Queue")
    task_status, task_issues = scan_tasks()
    report_lines.append(f"| Status | Count |")
    report_lines.append(f"|---|---|")
    for status, count in task_status.items():
        report_lines.append(f"| {status.title()} | {count} |")
        
    if task_issues:
        report_lines.append(f"\n**Issues Found:**")
        for issue in task_issues:
            # FAILED: is a failure, STUCK: is a warning
            if issue.startswith("FAILED"):
                report_lines.append(f"- ~~{issue}~~")
            else:
                report_lines.append(f"- **{issue}**")
    report_lines.append(f"")

    report_lines.append(f"## Prometheus Targets")
    promo_data = check_prometheus_targets()
    if promo_data.get("error"):
        report_lines.append(f"~~Could not fetch Prometheus data: {promo_data['error']}~~")
    else:
        summary = promo_data.get("data", {}).get("summary", {})
        report_lines.append(f"| Status | Count |")
        report_lines.append(f"|---|---|")
        report_lines.append(f"| Total | {summary.get('total', 0)} |")
        report_lines.append(f"| Up | {summary.get('up', 0)} |")
        report_lines.append(f"| Down | {summary.get('down', 0)} |")
        report_lines.append(f"")
        
        targets = promo_data.get("data", {}).get("activeTargets", [])
        if any(t['health'] != 'up' for t in targets):
            report_lines.append(f"**Unhealthy Targets:**")
            report_lines.append(f"| Job | Endpoint | Status | Error |")
            report_lines.append(f"|---|---|---|---|")
            for target in targets:
                if target['health'] != 'up':
                    job = target.get('scrapePool', 'N/A')
                    endpoint = target.get('scrapeUrl', 'N/A')
                    health = target.get('health', 'N/A').upper()
                    error = target.get('lastError', '')
                    report_lines.append(f"| {job} | `{endpoint}` | ~~{health}~~ | `{error}` |")

    return "\n".join(report_lines)

def main():
    """Main function to generate and write the report."""
    report_content = generate_report()
    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"audit_{date_str}.md"
    
    try:
        with open(filename, "w") as f:
            f.write(report_content)
        print(f"Successfully generated audit report: {filename}")
    except IOError as e:
        print(f"Error writing report to {filename}: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
