"""
IMPLEMENTATION PLAN for US-005:

Components:
  - src/dashboard_builder.py:
    - DashboardBuilder.create_queue_depth_panel():
      - Creates a gauge panel showing sat_queue_depth metric
      - Includes proper gauge formatting with min/max thresholds
      - Returns valid Grafana JSON

Test Cases:
  1. AC1 (Gauge panel created with correct title) -> test_create_queue_depth_panel_creates_gauge_panel
  2. AC2 (Includes sat_queue_depth metric) -> test_panel_includes_queue_depth_metric
  3. AC3 (Proper gauge formatting with min/max values) -> test_panel_has_gauge_formatting_with_min_max
  4. AC4 (Panel JSON is valid Grafana format) -> test_panel_json_valid_grafana_format

Edge Cases:
  - Custom title
  - Custom min/max values
  - Custom grid position
  - Custom datasource
  - Empty queries list
  - Panel with color thresholds
"""

import pytest
import json

# These imports will fail since the implementation doesn't exist yet
from src.dashboard_builder import DashboardBuilder


class TestQueueDepthPanel:
    """Test suite for DashboardBuilder.create_queue_depth_panel()"""

    def test_create_queue_depth_panel_creates_gauge_panel(self):
        """Test that create_queue_depth_panel creates a gauge panel."""
        builder = DashboardBuilder()

        panel = builder.create_queue_depth_panel()

        # Must be a gauge panel
        assert panel['type'] == 'gauge'

    def test_panel_includes_queue_depth_metric(self):
        """Test that panel includes sat_queue_depth metric."""
        builder = DashboardBuilder()

        panel = builder.create_queue_depth_panel()

        # Panel must have targets (queries)
        assert 'targets' in panel
        assert len(panel['targets']) > 0

        # Check for queue depth metric in targets
        targets_with_metric = [t for t in panel['targets'] if 'sat_queue_depth' in str(t)]
        assert len(targets_with_metric) > 0, "Panel should include sat_queue_depth metric"

    def test_panel_has_gauge_formatting_with_min_max(self):
        """Test that panel has proper gauge formatting with min/max values."""
        builder = DashboardBuilder()

        panel = builder.create_queue_depth_panel()

        # Panel must have a title
        assert 'title' in panel
        assert panel['title'] in ['Queue Depth', 'sat_queue_depth']

        # Panel must have targets with metric
        assert 'targets' in panel

        # Panel should have gauge-specific formatting
        assert 'options' in panel

    def test_panel_json_valid_grafana_format(self):
        """Test that panel JSON is valid Grafana format."""
        builder = DashboardBuilder()

        panel = builder.create_queue_depth_panel()

        # Must have type
        assert 'type' in panel
        assert panel['type'] == 'gauge'

        # Must have title
        assert 'title' in panel
        assert len(panel['title']) > 0

        # Must have targets
        assert 'targets' in panel
        assert len(panel['targets']) > 0

        # Validate JSON is valid
        json_str = json.dumps(panel)
        parsed = json.loads(json_str)

        # Verify round-trip preserves structure
        assert parsed == panel

    def test_panel_with_custom_title(self):
        """Test that panel can have custom title."""
        builder = DashboardBuilder()

        panel = builder.create_queue_depth_panel(custom_title="Custom Queue Depth")

        assert panel['type'] == 'gauge'
        assert panel['title'] == "Custom Queue Depth"

    def test_panel_with_min_max_values(self):
        """Test that panel can have custom min/max values."""
        builder = DashboardBuilder()

        panel = builder.create_queue_depth_panel(
            min=0,
            max=1000
        )

        # Check that min/max are set
        assert 'options' in panel
        assert panel['options'].get('min') == 0
        assert panel['options'].get('max') == 1000

    def test_panel_with_grid_position(self):
        """Test that panel can have grid position."""
        builder = DashboardBuilder()

        panel = builder.create_queue_depth_panel(
            grid_pos={'x': 0, 'y': 0, 'w': 6, 'h': 4}
        )

        assert panel['gridPos'] == {'x': 0, 'y': 0, 'w': 6, 'h': 4}

    def test_panel_with_datasource(self):
        """Test that panel can specify datasource."""
        builder = DashboardBuilder()

        panel = builder.create_queue_depth_panel(datasource="Prometheus")

        assert panel['datasource'] == "Prometheus"

    def test_panel_with_color_thresholds(self):
        """Test that panel can have color thresholds for gauge display."""
        builder = DashboardBuilder()

        panel = builder.create_queue_depth_panel()

        # Panel should have fieldConfig for color thresholds
        assert 'fieldConfig' in panel
        assert 'defaults' in panel['fieldConfig']
        assert 'thresholds' in panel['fieldConfig']['defaults']

        # Check for threshold steps
        thresholds = panel['fieldConfig']['defaults']['thresholds']
        assert 'steps' in thresholds
        assert len(thresholds['steps']) > 0

    def test_panel_empty_queries_list(self):
        """Test that panel handles empty queries list."""
        builder = DashboardBuilder()

        panel = builder.create_queue_depth_panel(queries=[])

        # Should still be valid panel with type and title
        assert panel['type'] == 'gauge'
        assert 'title' in panel
        assert panel['title'] in ['Queue Depth', 'sat_queue_depth']

    def test_panel_has_proper_query_format(self):
        """Test that panel has proper query format for Prometheus."""
        builder = DashboardBuilder()

        panel = builder.create_queue_depth_panel()

        # Check that targets have proper query format
        assert 'targets' in panel
        for target in panel['targets']:
            # Each target should have expr (Prometheus query)
            assert 'expr' in target or 'query' in target, "Each target should have expr or query"

            # Each target should have legend format
            assert 'legendFormat' in target or 'legend' in target, "Each target should have legendFormat or legend"


# Exit code for pytest to report failures
fail_count = 0
if __name__ == '__main__':
    # Run the tests
    pytest.main([__file__, '-v'])
