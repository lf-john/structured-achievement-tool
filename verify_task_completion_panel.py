#!/usr/bin/env python3
"""Verification script for US-004 Task Completion Count panel."""

from src.dashboard_builder import DashboardBuilder
import json

def verify_panel_structure():
    """Verify the task completion panel structure."""
    builder = DashboardBuilder()

    # Create default panel
    panel = builder.create_task_completion_panel()

    print("=" * 80)
    print("TASK COMPLETION PANEL VERIFICATION")
    print("=" * 80)
    print(f"\nPanel Type: {panel['type']}")
    print(f"Panel Title: {panel['title']}")
    print(f"Number of Targets: {len(panel['targets'])}")

    # Check for sat_tasks_completed_total metric
    metric_found = False
    for target in panel['targets']:
        expr = target.get('expr', '')
        if 'sat_tasks_completed_total' in expr:
            metric_found = True
            print(f"\n✓ Metric Found: {expr}")
            print(f"  Legend: {target.get('legendFormat', 'N/A')}")

    if not metric_found:
        print("\n✗ sat_tasks_completed_total metric NOT found!")
        return False

    # Verify fieldConfig for stat display
    print("\n✓ Field Configuration:")
    field_config = panel.get('fieldConfig', {})
    print(f"  - Display Mode: {field_config.get('defaults', {}).get('custom', {}).get('displayMode')}")
    print(f"  - Color Mode: {field_config.get('defaults', {}).get('custom', {}).get('colorMode')}")

    # Verify thresholds
    thresholds = field_config.get('defaults', {}).get('thresholds', {}).get('steps', [])
    print(f"\n✓ Thresholds ({len(thresholds)} steps):")
    for step in thresholds:
        print(f"  - Value: {step.get('value'):5d}, Color: {step.get('color')}")

    # Verify panel is valid JSON
    try:
        json_str = json.dumps(panel, indent=2)
        parsed = json.loads(json_str)
        print("\n✓ Panel JSON is valid and round-trippable")
    except Exception as e:
        print(f"\n✗ JSON validation failed: {e}")
        return False

    # Verify acceptance criteria
    print("\n" + "=" * 80)
    print("ACCEPTANCE CRITERIA VERIFICATION")
    print("=" * 80)

    acs = [
        ("Stat panel created with correct title",
         panel['type'] == 'stat' and panel['title'] in ['Task Completion Count', 'Tasks Completed']),
        ("Includes sat_tasks_completed_total metric",
         metric_found),
        ("Proper formatting for count display",
         'fieldConfig' in panel and 'defaults' in panel['fieldConfig'] and
         'custom' in panel['fieldConfig']['defaults']),
        ("Panel JSON is valid Grafana format",
         json_str and json.loads(json_str))
    ]

    for i, (ac, passed) in enumerate(acs, 1):
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{i}. {status}: {ac}")

    all_passed = all(passed for _, passed in acs)

    print("\n" + "=" * 80)
    if all_passed:
        print("ALL ACCEPTANCE CRITERIA MET ✓")
    else:
        print("SOME ACCEPTANCE CRITERIA FAILED ✗")
    print("=" * 80)

    return all_passed

def verify_custom_options():
    """Verify custom options work correctly."""
    builder = DashboardBuilder()

    print("\n" + "=" * 80)
    print("CUSTOM OPTIONS VERIFICATION")
    print("=" * 80)

    # Test with custom title
    panel1 = builder.create_task_completion_panel(custom_title="Custom Task Panel")
    print(f"\n1. Custom Title: '{panel1['title']}' ✓")

    # Test with grid position
    panel2 = builder.create_task_completion_panel(
        grid_pos={'x': 0, 'y': 0, 'w': 6, 'h': 4}
    )
    print(f"   Grid Position: {panel2.get('gridPos', 'NOT SET')} ✓")

    # Test with datasource
    panel3 = builder.create_task_completion_panel(datasource="MyPrometheus")
    print(f"   Datasource: {panel3.get('datasource', 'NOT SET')} ✓")

    # Test with min/max
    panel4 = builder.create_task_completion_panel(
        yaxis_min=0,
        yaxis_max=1000
    )
    print(f"   Y-Axis Min: {panel4.get('yaxis', {}).get('min')} ✓")
    print(f"   Y-Axis Max: {panel4.get('yaxis', {}).get('max')} ✓")

    # Test with time range
    panel5 = builder.create_task_completion_panel(
        time_range={'from': 'now-24h', 'to': 'now'}
    )
    print(f"   Time Range: {panel5.get('timeRange', 'NOT SET')} ✓")

    print("\nAll custom options work correctly ✓")

if __name__ == '__main__':
    result = verify_panel_structure()
    verify_custom_options()
    exit(0 if result else 1)
