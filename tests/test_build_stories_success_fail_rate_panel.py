"""
IMPLEMENTATION PLAN for US-003:

Components:
  - src/dashboard_builder.py:
    - DashboardBuilder.create_stories_success_fail_panel():
      - Creates a time series panel showing sat_stories_succeeded_total and sat_stories_failed_total
      - Includes proper legends and metric labels
      - Returns valid Grafana JSON

Test Cases:
  1. AC1 (Time series panel created) -> test_create_stories_success_fail_panel_creates_time_series_panel
  2. AC2 (Includes sat_stories_succeeded_total) -> test_panel_includes_succeeded_metric
  3. AC3 (Includes sat_stories_failed_total) -> test_panel_includes_failed_metric
  4. AC4 (Proper metric labels and legends) -> test_panel_has_proper_legends_and_labels
  5. AC5 (Panel JSON is valid Grafana format) -> test_panel_json_valid_grafana_format

Edge Cases:
  - Empty queries list (should handle gracefully)
  - None options (should use defaults)
  - Panel with custom grid position
  - Panel with custom datasource
"""

import json

import pytest

# These imports will fail since the implementation doesn't exist yet
from src.dashboard_builder import DashboardBuilder


class TestStoriesSuccessFailRatePanel:
    """Test suite for DashboardBuilder.create_stories_success_fail_panel()"""

    def test_create_stories_success_fail_panel_creates_time_series_panel(self):
        """Test that create_stories_success_fail_panel creates a time series panel."""
        builder = DashboardBuilder()

        panel = builder.create_stories_success_fail_panel()

        # Must be a time series panel
        assert panel['type'] == 'timeseries'

    def test_panel_includes_succeeded_metric(self):
        """Test that panel includes sat_stories_succeeded_total metric."""
        builder = DashboardBuilder()

        panel = builder.create_stories_success_fail_panel()

        # Panel must have targets (queries)
        assert 'targets' in panel
        assert len(panel['targets']) > 0

        # Check for succeeded metric in targets
        targets_with_succeeded = [t for t in panel['targets'] if 'sat_stories_succeeded_total' in str(t)]
        assert len(targets_with_succeeded) > 0, "Panel should include sat_stories_succeeded_total metric"

    def test_panel_includes_failed_metric(self):
        """Test that panel includes sat_stories_failed_total metric."""
        builder = DashboardBuilder()

        panel = builder.create_stories_success_fail_panel()

        # Check for failed metric in targets
        targets_with_failed = [t for t in panel['targets'] if 'sat_stories_failed_total' in str(t)]
        assert len(targets_with_failed) > 0, "Panel should include sat_stories_failed_total metric"

    def test_panel_has_proper_legends_and_labels(self):
        """Test that panel has proper legends and metric labels."""
        builder = DashboardBuilder()

        panel = builder.create_stories_success_fail_panel()

        # Panel must have a title
        assert 'title' in panel

        # Panel must have targets with legends
        assert 'targets' in panel
        for target in panel['targets']:
            # Each target should have a legend
            assert 'legend' in target or 'legendFormat' in target, "Each target should have a legend"

    def test_panel_json_valid_grafana_format(self):
        """Test that panel JSON is valid Grafana format."""
        builder = DashboardBuilder()

        panel = builder.create_stories_success_fail_panel()

        # Must have type
        assert 'type' in panel

        # Must have title
        assert 'title' in panel

        # Must have targets
        assert 'targets' in panel

        # Validate JSON is valid
        json_str = json.dumps(panel)
        parsed = json.loads(json_str)

        # Verify round-trip preserves structure
        assert parsed == panel

    def test_panel_with_custom_title(self):
        """Test that panel can have custom title."""
        builder = DashboardBuilder()

        panel = builder.create_stories_success_fail_panel(custom_title="Custom Stories Panel")

        assert panel['type'] == 'timeseries'
        assert panel['title'] == "Custom Stories Panel"

    def test_panel_with_grid_position(self):
        """Test that panel can have grid position."""
        builder = DashboardBuilder()

        panel = builder.create_stories_success_fail_panel(
            grid_pos={'x': 0, 'y': 0, 'w': 12, 'h': 8}
        )

        assert panel['gridPos'] == {'x': 0, 'y': 0, 'w': 12, 'h': 8}

    def test_panel_with_datasource(self):
        """Test that panel can specify datasource."""
        builder = DashboardBuilder()

        panel = builder.create_stories_success_fail_panel(datasource="Prometheus")

        assert panel['datasource'] == "Prometheus"

    def test_panel_with_min_max(self):
        """Test that panel can have min/max y-axis options."""
        builder = DashboardBuilder()

        panel = builder.create_stories_success_fail_panel(
            yaxis_min=0,
            yaxis_max=100
        )

        assert panel['yaxis']['min'] == 0
        assert panel['yaxis']['max'] == 100

    def test_panel_with_time_range(self):
        """Test that panel can specify custom time range."""
        builder = DashboardBuilder()

        panel = builder.create_stories_success_fail_panel(
            time_range={'from': 'now-24h', 'to': 'now'}
        )

        assert panel['timeRange'] == {'from': 'now-24h', 'to': 'now'}

    def test_panel_empty_queries_list(self):
        """Test that panel handles empty queries list."""
        builder = DashboardBuilder()

        panel = builder.create_stories_success_fail_panel(queries=[])

        # Should still be valid panel with type and title
        assert panel['type'] == 'timeseries'
        assert 'title' in panel
        assert panel['title'] in ['Stories Success/Fail Rate']


# Exit code for pytest to report failures
fail_count = 0
if __name__ == '__main__':
    # Run the tests
    pytest.main([__file__, '-v'])
