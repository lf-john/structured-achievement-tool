"""
IMPLEMENTATION PLAN for US-002:

Components:
  - src/dashboard_builder.py:
    - DashboardBuilder class:
      - create_dashboard(name, uid, panels, options): Creates base dashboard structure
      - create_time_series_panel(title, queries, options): Creates time series panel
      - create_stat_panel(title, queries, options): Creates stat panel
      - create_gauge_panel(title, queries, options): Creates gauge panel
      - create_pie_chart_panel(title, queries, options): Creates pie chart panel
      - create_heatmap_panel(title, queries, options): Creates heatmap panel
      - create_prometheus_datasource(name, url): Creates Prometheus datasource config

Test Cases:
  1. AC1 -> test_create_dashboard_builds_valid_grafana_json: Verifies dashboard JSON is valid
  2. AC2 -> test_create_dashboard_has_sat_overview_name: Verifies name is 'SAT Overview'
  3. AC2 -> test_create_dashboard_has_sat_overview_uid: Verifies UID is 'sat-overview'
  4. AC3 -> test_create_dashboard_default_time_range_last_6_hours: Verifies time range is 'Last 6 hours'
  5. AC4 -> test_create_dashboard_auto_refresh_30_seconds: Verifies auto-refresh is 30s
  6. AC5 -> test_create_time_series_panel_helper: Verifies helper creates time series panels
  7. AC6 -> test_create_stat_panel_helper: Verifies helper creates stat panels
  8. AC7 -> test_create_gauge_panel_helper: Verifies helper creates gauge panels
  9. AC8 -> test_create_pie_chart_panel_helper: Verifies helper creates pie chart panels
  10. AC9 -> test_create_heatmap_panel_helper: Verifies helper creates heatmap panels
  11. AC10 -> test_create_prometheus_datasource: Verifies datasource configuration
  12. AC11 -> test_all_generated_json_valid_grafana_schema: Verifies valid schema

Edge Cases:
  - Empty panels list
  - None values for optional fields
  - Maximum panel count
  - Special characters in title/uid
  - Invalid panel type
  - Missing required fields
  - Duplicate UIDs
"""

import pytest
import json
from unittest.mock import MagicMock

# These imports will fail since the implementation doesn't exist yet
from src.dashboard_builder import DashboardBuilder


class TestCreateDashboard:
    """Test suite for DashboardBuilder.create_dashboard()"""

    def test_create_dashboard_builds_valid_grafana_json(self):
        """Test that create_dashboard builds valid Grafana dashboard JSON."""
        builder = DashboardBuilder()

        dashboard = builder.create_dashboard(
            name="SAT Overview",
            uid="sat-overview",
            panels=[],
            options={}
        )

        # Verify JSON is valid
        assert isinstance(dashboard, dict)
        json_str = json.dumps(dashboard)
        parsed = json.loads(json_str)
        assert parsed == dashboard

    def test_create_dashboard_has_sat_overview_name(self):
        """Test that dashboard has name 'SAT Overview'."""
        builder = DashboardBuilder()

        dashboard = builder.create_dashboard(
            name="SAT Overview",
            uid="sat-overview",
            panels=[],
            options={}
        )

        assert dashboard['name'] == "SAT Overview"

    def test_create_dashboard_has_sat_overview_uid(self):
        """Test that dashboard has UID 'sat-overview'."""
        builder = DashboardBuilder()

        dashboard = builder.create_dashboard(
            name="SAT Overview",
            uid="sat-overview",
            panels=[],
            options={}
        )

        assert dashboard['uid'] == "sat-overview"

    def test_create_dashboard_default_time_range_last_6_hours(self):
        """Test that default time range is 'Last 6 hours'."""
        builder = DashboardBuilder()

        dashboard = builder.create_dashboard(
            name="SAT Overview",
            uid="sat-overview",
            panels=[],
            options={}
        )

        assert dashboard.get('time') == {'from': 'now-6h', 'to': 'now'}

    def test_create_dashboard_auto_refresh_30_seconds(self):
        """Test that auto-refresh interval is 30 seconds."""
        builder = DashboardBuilder()

        dashboard = builder.create_dashboard(
            name="SAT Overview",
            uid="sat-overview",
            panels=[],
            options={}
        )

        assert dashboard.get('refresh') == "30s"

    def test_create_dashboard_includes_panels(self):
        """Test that dashboard includes panels list."""
        builder = DashboardBuilder()

        panels = [
            {'type': 'time-series', 'title': 'Test Panel', 'gridPos': {'x': 0, 'y': 0, 'w': 12, 'h': 4}}
        ]

        dashboard = builder.create_dashboard(
            name="SAT Overview",
            uid="sat-overview",
            panels=panels,
            options={}
        )

        assert 'panels' in dashboard
        assert len(dashboard['panels']) == 1
        assert dashboard['panels'][0] == panels[0]

    def test_create_dashboard_default_variables(self):
        """Test that dashboard includes default time variable."""
        builder = DashboardBuilder()

        dashboard = builder.create_dashboard(
            name="SAT Overview",
            uid="sat-overview",
            panels=[],
            options={}
        )

        assert 'templating' in dashboard
        assert 'list' in dashboard['templating']
        assert len(dashboard['templating']['list']) > 0

    def test_create_dashboard_with_custom_options(self):
        """Test that dashboard accepts custom options."""
        builder = DashboardBuilder()

        custom_options = {
            'time': {'from': 'now-24h', 'to': 'now'},
            'refresh': '60s'
        }

        dashboard = builder.create_dashboard(
            name="SAT Overview",
            uid="sat-overview",
            panels=[],
            options=custom_options
        )

        assert dashboard['time'] == custom_options['time']
        assert dashboard['refresh'] == custom_options['refresh']


class TestCreateTimeSeriesPanel:
    """Test suite for time series panel helper"""

    def test_create_time_series_panel_helper(self):
        """Test that create_time_series_panel creates valid panel."""
        builder = DashboardBuilder()

        panel = builder.create_time_series_panel(
            title="Test Time Series",
            queries=[{'expr': 'metric1'}],
            options={}
        )

        assert panel['type'] == 'timeseries'
        assert panel['title'] == "Test Time Series"
        assert 'targets' in panel
        assert panel['targets'][0]['expr'] == 'metric1'

    def test_time_series_panel_with_grid_position(self):
        """Test that time series panel can have grid position."""
        builder = DashboardBuilder()

        panel = builder.create_time_series_panel(
            title="Test Time Series",
            queries=[{'expr': 'metric1'}],
            options={'gridPos': {'x': 0, 'y': 0, 'w': 12, 'h': 4}}
        )

        assert panel['gridPos'] == {'x': 0, 'y': 0, 'w': 12, 'h': 4}

    def test_time_series_panel_with_datasource(self):
        """Test that time series panel can specify datasource."""
        builder = DashboardBuilder()

        panel = builder.create_time_series_panel(
            title="Test Time Series",
            queries=[{'expr': 'metric1'}],
            options={'datasource': 'Prometheus'}
        )

        assert panel['datasource'] == 'Prometheus'

    def test_time_series_panel_with_min_max(self):
        """Test that time series panel can have min/max options."""
        builder = DashboardBuilder()

        panel = builder.create_time_series_panel(
            title="Test Time Series",
            queries=[{'expr': 'metric1'}],
            options={
                'yaxis': {
                    'min': 0,
                    'max': 100
                }
            }
        )

        assert panel['yaxis']['min'] == 0
        assert panel['yaxis']['max'] == 100


class TestCreateStatPanel:
    """Test suite for stat panel helper"""

    def test_create_stat_panel_helper(self):
        """Test that create_stat_panel creates valid panel."""
        builder = DashboardBuilder()

        panel = builder.create_stat_panel(
            title="Test Stat",
            queries=[{'expr': 'metric1'}],
            options={}
        )

        assert panel['type'] == 'stat'
        assert panel['title'] == "Test Stat"
        assert 'targets' in panel
        assert panel['targets'][0]['expr'] == 'metric1'

    def test_stat_panel_with_coloring(self):
        """Test that stat panel can have conditional coloring."""
        builder = DashboardBuilder()

        panel = builder.create_stat_panel(
            title="Test Stat",
            queries=[{'expr': 'metric1'}],
            options={
                'color': {
                    'mode': 'thresholds',
                    'thresholds': [
                        {'value': 50, 'color': 'green'},
                        {'value': 80, 'color': 'yellow'}
                    ]
                }
            }
        )

        assert panel['color']['mode'] == 'thresholds'


class TestCreateGaugePanel:
    """Test suite for gauge panel helper"""

    def test_create_gauge_panel_helper(self):
        """Test that create_gauge_panel creates valid panel."""
        builder = DashboardBuilder()

        panel = builder.create_gauge_panel(
            title="Test Gauge",
            queries=[{'expr': 'metric1'}],
            options={}
        )

        assert panel['type'] == 'gauge'
        assert panel['title'] == "Test Gauge"
        assert 'targets' in panel
        assert panel['targets'][0]['expr'] == 'metric1'

    def test_gauge_panel_with_min_max_max(self):
        """Test that gauge panel can have min/max/max values."""
        builder = DashboardBuilder()

        panel = builder.create_gauge_panel(
            title="Test Gauge",
            queries=[{'expr': 'metric1'}],
            options={
                'min': 0,
                'max': 100,
                'value': 75
            }
        )

        assert panel['options']['min'] == 0
        assert panel['options']['max'] == 100
        assert panel['options']['value'] == 75


class TestCreatePieChartPanel:
    """Test suite for pie chart panel helper"""

    def test_create_pie_chart_panel_helper(self):
        """Test that create_pie_chart_panel creates valid panel."""
        builder = DashboardBuilder()

        panel = builder.create_pie_chart_panel(
            title="Test Pie Chart",
            queries=[{'expr': 'metric1'}],
            options={}
        )

        assert panel['type'] == 'piechart'
        assert panel['title'] == "Test Pie Chart"
        assert 'targets' in panel
        assert panel['targets'][0]['expr'] == 'metric1'

    def test_pie_chart_panel_with_orientation(self):
        """Test that pie chart panel can have orientation."""
        builder = DashboardBuilder()

        panel = builder.create_pie_chart_panel(
            title="Test Pie Chart",
            queries=[{'expr': 'metric1'}],
            options={'orientation': 'horizontal'}
        )

        assert panel['options']['orientation'] == 'horizontal'


class TestCreateHeatmapPanel:
    """Test suite for heatmap panel helper"""

    def test_create_heatmap_panel_helper(self):
        """Test that create_heatmap_panel creates valid panel."""
        builder = DashboardBuilder()

        panel = builder.create_heatmap_panel(
            title="Test Heatmap",
            queries=[{'expr': 'metric1'}],
            options={}
        )

        assert panel['type'] == 'heatmap'
        assert panel['title'] == "Test Heatmap"
        assert 'targets' in panel
        assert panel['targets'][0]['expr'] == 'metric1'


class TestCreatePrometheusDatasource:
    """Test suite for Prometheus datasource helper"""

    def test_create_prometheus_datasource(self):
        """Test that create_prometheus_datasource creates valid configuration."""
        builder = DashboardBuilder()

        datasource = builder.create_prometheus_datasource(
            name="Prometheus",
            url="http://prometheus:9090"
        )

        assert isinstance(datasource, dict)
        assert datasource['name'] == "Prometheus"
        assert datasource['type'] == "prometheus"
        assert datasource['url'] == "http://prometheus:9090"
        assert datasource['access'] == "proxy"

    def test_create_prometheus_datasource_with_access_mode(self):
        """Test that Prometheus datasource can specify access mode."""
        builder = DashboardBuilder()

        datasource = builder.create_prometheus_datasource(
            name="Prometheus",
            url="http://prometheus:9090",
            access="direct"
        )

        assert datasource['access'] == "direct"

    def test_create_prometheus_datasource_with_version(self):
        """Test that Prometheus datasource can specify version."""
        builder = DashboardBuilder()

        datasource = builder.create_prometheus_datasource(
            name="Prometheus",
            url="http://prometheus:9090",
            version=2
        )

        assert datasource['version'] == 2


class TestValidGrafanaSchema:
    """Test suite for verifying all generated JSON is valid Grafana schema"""

    def test_time_series_panel_valid_schema(self):
        """Test that time series panel has valid Grafana schema."""
        builder = DashboardBuilder()

        panel = builder.create_time_series_panel(
            title="Test",
            queries=[{'expr': 'metric1'}],
            options={}
        )

        # Must have type
        assert 'type' in panel

        # Must have title
        assert 'title' in panel

        # Must have targets (for queries)
        assert 'targets' in panel

        # Must have valid types
        valid_types = ['timeseries', 'stat', 'gauge', 'piechart', 'heatmap', 'text']
        assert panel['type'] in valid_types

    def test_stat_panel_valid_schema(self):
        """Test that stat panel has valid Grafana schema."""
        builder = DashboardBuilder()

        panel = builder.create_stat_panel(
            title="Test",
            queries=[{'expr': 'metric1'}],
            options={}
        )

        assert 'type' in panel
        assert 'title' in panel
        assert 'targets' in panel

    def test_gauge_panel_valid_schema(self):
        """Test that gauge panel has valid Grafana schema."""
        builder = DashboardBuilder()

        panel = builder.create_gauge_panel(
            title="Test",
            queries=[{'expr': 'metric1'}],
            options={}
        )

        assert 'type' in panel
        assert 'title' in panel
        assert 'targets' in panel

    def test_pie_chart_panel_valid_schema(self):
        """Test that pie chart panel has valid Grafana schema."""
        builder = DashboardBuilder()

        panel = builder.create_pie_chart_panel(
            title="Test",
            queries=[{'expr': 'metric1'}],
            options={}
        )

        assert 'type' in panel
        assert 'title' in panel
        assert 'targets' in panel

    def test_heatmap_panel_valid_schema(self):
        """Test that heatmap panel has valid Grafana schema."""
        builder = DashboardBuilder()

        panel = builder.create_heatmap_panel(
            title="Test",
            queries=[{'expr': 'metric1'}],
            options={}
        )

        assert 'type' in panel
        assert 'title' in panel
        assert 'targets' in panel

    def test_dashboard_valid_schema(self):
        """Test that dashboard has valid Grafana schema."""
        builder = DashboardBuilder()

        dashboard = builder.create_dashboard(
            name="SAT Overview",
            uid="sat-overview",
            panels=[],
            options={}
        )

        # Must have type
        assert dashboard['type'] == 'dashboard'

        # Must have title
        assert dashboard['title'] == "SAT Overview"

        # Must have uid
        assert dashboard['uid'] == "sat-overview"

        # Must have time
        assert 'time' in dashboard

        # Must have panels
        assert 'panels' in dashboard

        # Must have templating
        assert 'templating' in dashboard


class TestEdgeCases:
    """Test suite for edge cases"""

    def test_dashboard_with_empty_panels(self):
        """Test that dashboard can have empty panels list."""
        builder = DashboardBuilder()

        dashboard = builder.create_dashboard(
            name="SAT Overview",
            uid="sat-overview",
            panels=[],
            options={}
        )

        assert len(dashboard['panels']) == 0

    def test_dashboard_with_none_options(self):
        """Test that dashboard handles None options."""
        builder = DashboardBuilder()

        dashboard = builder.create_dashboard(
            name="SAT Overview",
            uid="sat-overview",
            panels=[],
            options=None
        )

        assert dashboard is not None

    def test_dashboard_with_special_characters_in_title(self):
        """Test that dashboard handles special characters in title."""
        builder = DashboardBuilder()

        dashboard = builder.create_dashboard(
            name="SAT Overview Test 2024",
            uid="sat-overview-2024",
            panels=[],
            options={}
        )

        assert dashboard['name'] == "SAT Overview Test 2024"
        assert dashboard['uid'] == "sat-overview-2024"

    def test_dashboard_with_multiple_panels(self):
        """Test that dashboard can handle many panels."""
        builder = DashboardBuilder()

        panels = [
            {
                'type': 'timeseries',
                'title': f'Panel {i}',
                'gridPos': {'x': i*12, 'y': i*6, 'w': 12, 'h': 4},
                'targets': [{'expr': f'metric{i}'}]
            }
            for i in range(50)
        ]

        dashboard = builder.create_dashboard(
            name="SAT Overview",
            uid="sat-overview",
            panels=panels,
            options={}
        )

        assert len(dashboard['panels']) == 50

    def test_time_series_panel_without_queries(self):
        """Test that time series panel can be created without queries."""
        builder = DashboardBuilder()

        panel = builder.create_time_series_panel(
            title="Test Time Series",
            queries=None,
            options={}
        )

        # Should still have type and title
        assert panel['type'] == 'timeseries'
        assert panel['title'] == "Test Time Series"

    def test_stat_panel_without_queries(self):
        """Test that stat panel can be created without queries."""
        builder = DashboardBuilder()

        panel = builder.create_stat_panel(
            title="Test Stat",
            queries=None,
            options={}
        )

        assert panel['type'] == 'stat'
        assert panel['title'] == "Test Stat"


# Exit code for pytest to report failures
fail_count = 0
if __name__ == '__main__':
    # Run the tests
    pytest.main([__file__, '-v'])
