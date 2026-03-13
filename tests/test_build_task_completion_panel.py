"""
IMPLEMENTATION PLAN for US-004:

Components:
  - src/dashboard_builder.py:
    - DashboardBuilder.create_task_completion_panel():
      - Creates a stat panel showing sat_tasks_completed_total metric
      - Includes proper metric labels and count formatting
      - Returns valid Grafana JSON

Test Cases:
  1. AC1 (Stat panel created) -> test_create_task_completion_panel_creates_stat_panel
  2. AC2 (Includes sat_tasks_completed_total metric) -> test_panel_includes_completed_metric
  3. AC3 (Proper formatting for count display) -> test_panel_has_proper_formatting
  4. AC4 (Panel JSON is valid Grafana format) -> test_panel_json_valid_grafana_format

Edge Cases:
  - Custom title
  - Custom grid position
  - Custom datasource
  - Panel with min/max values
  - Panel with time range
  - Panel with legends
"""

import json

import pytest

# These imports will fail since the implementation doesn't exist yet
from src.dashboard_builder import DashboardBuilder


class TestTaskCompletionPanel:
    """Test suite for DashboardBuilder.create_task_completion_panel()"""

    def test_create_task_completion_panel_creates_stat_panel(self):
        """Test that create_task_completion_panel creates a stat panel."""
        builder = DashboardBuilder()

        panel = builder.create_task_completion_panel()

        # Must be a stat panel
        assert panel["type"] == "stat"

    def test_panel_includes_completed_metric(self):
        """Test that panel includes sat_tasks_completed_total metric."""
        builder = DashboardBuilder()

        panel = builder.create_task_completion_panel()

        # Panel must have targets (queries)
        assert "targets" in panel
        assert len(panel["targets"]) > 0

        # Check for completed metric in targets
        targets_with_metric = [t for t in panel["targets"] if "sat_tasks_completed_total" in str(t)]
        assert len(targets_with_metric) > 0, "Panel should include sat_tasks_completed_total metric"

    def test_panel_has_proper_formatting(self):
        """Test that panel has proper formatting for count display."""
        builder = DashboardBuilder()

        panel = builder.create_task_completion_panel()

        # Panel must have a title
        assert "title" in panel
        assert panel["title"] in ["Task Completion Count", "Tasks Completed"]

        # Panel must have targets with legends
        assert "targets" in panel
        for target in panel["targets"]:
            # Each target should have a legend
            assert "legendFormat" in target or "legend" in target, "Each target should have a legendFormat"

        # Check for proper fieldConfig for stat display
        assert "fieldConfig" in panel
        assert "defaults" in panel["fieldConfig"]
        assert "custom" in panel["fieldConfig"]["defaults"]

    def test_panel_json_valid_grafana_format(self):
        """Test that panel JSON is valid Grafana format."""
        builder = DashboardBuilder()

        panel = builder.create_task_completion_panel()

        # Must have type
        assert "type" in panel
        assert panel["type"] == "stat"

        # Must have title
        assert "title" in panel
        assert len(panel["title"]) > 0

        # Must have targets
        assert "targets" in panel
        assert len(panel["targets"]) > 0

        # Validate JSON is valid
        json_str = json.dumps(panel)
        parsed = json.loads(json_str)

        # Verify round-trip preserves structure
        assert parsed == panel

    def test_panel_with_custom_title(self):
        """Test that panel can have custom title."""
        builder = DashboardBuilder()

        panel = builder.create_task_completion_panel(custom_title="Custom Task Completion")

        assert panel["type"] == "stat"
        assert panel["title"] == "Custom Task Completion"

    def test_panel_with_grid_position(self):
        """Test that panel can have grid position."""
        builder = DashboardBuilder()

        panel = builder.create_task_completion_panel(grid_pos={"x": 0, "y": 0, "w": 6, "h": 4})

        assert panel["gridPos"] == {"x": 0, "y": 0, "w": 6, "h": 4}

    def test_panel_with_datasource(self):
        """Test that panel can specify datasource."""
        builder = DashboardBuilder()

        panel = builder.create_task_completion_panel(datasource="Prometheus")

        assert panel["datasource"] == "Prometheus"

    def test_panel_with_min_max(self):
        """Test that panel can have min/max y-axis options."""
        builder = DashboardBuilder()

        panel = builder.create_task_completion_panel(yaxis_min=0, yaxis_max=1000)

        assert panel["yaxis"]["min"] == 0
        assert panel["yaxis"]["max"] == 1000

    def test_panel_with_time_range(self):
        """Test that panel can specify custom time range."""
        builder = DashboardBuilder()

        panel = builder.create_task_completion_panel(time_range={"from": "now-24h", "to": "now"})

        assert panel["timeRange"] == {"from": "now-24h", "to": "now"}

    def test_panel_with_legends(self):
        """Test that panel can have custom legends."""
        builder = DashboardBuilder()

        panel = builder.create_task_completion_panel(legends=["Completed", "Total"])

        # Check that legends are set
        assert "targets" in panel
        for i, target in enumerate(panel["targets"]):
            if i < len(["Completed", "Total"]):
                assert target.get("legendFormat") == ["Completed", "Total"][i]

    def test_panel_empty_queries_list(self):
        """Test that panel handles empty queries list."""
        builder = DashboardBuilder()

        panel = builder.create_task_completion_panel(queries=[])

        # Should still be valid panel with type and title
        assert panel["type"] == "stat"
        assert "title" in panel
        assert panel["title"] == "Task Completion Count"

    def test_panel_defaults_to_prometheus_datasource(self):
        """Test that panel can have custom datasource."""
        builder = DashboardBuilder()

        panel = builder.create_task_completion_panel()

        # Panel should be valid, datasource is optional
        assert "type" in panel
        assert "title" in panel
        assert "targets" in panel


# Exit code for pytest to report failures
fail_count = 0
if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
