"""
IMPLEMENTATION PLAN for US-006:

Components:
  - src/dashboard_builder.py:
    - DashboardBuilder.create_provider_usage_panel():
      - Creates a pie chart panel showing Provider Usage Breakdown metric
      - Defaults: title='Provider Usage Breakdown', metric='sat_provider_requests_total', grouped by provider
      - Supports: custom_title, grid_pos, datasource, queries parameters

Test Cases:
  1. AC1 -> test_panel_has_correct_title: Verifies default title is 'Provider Usage Breakdown'
  2. AC2 -> test_panel_uses_correct_metric: Verifies metric expression is correct
  3. AC3 -> test_panel_groups_by_provider: Verifies legendFormat for provider grouping
  4. AC4 -> test_panel_has_piechart_formatting: Verifies pie chart display settings
  5. AC5 -> test_panel_is_valid_grafana_json: Verifies JSON serialization
  6. test_with_custom_title: Verifies custom title parameter works
  7. test_with_custom_datasource: Verifies datasource parameter works
  8. test_with_custom_grid_pos: Verifies grid position parameter works
  9. test_with_custom_queries: Verifies custom queries parameter works
  10. test_panel_has_field_config: Verifies fieldConfig structure exists
  11. test_panel_default_options: Verifies default legend and tooltip settings
  12. test_panel_with_empty_queries: Verifies empty queries handling
  13. test_panel_with_special_chars_in_title: Verifies special characters in title

Edge Cases:
  - Empty queries list
  - None values for optional parameters
  - Special characters in custom titles
  - Multiple providers in data
"""

import pytest
import json
from src.dashboard_builder import DashboardBuilder

class TestCreateProviderUsagePanel:
    """Test suite for DashboardBuilder.create_provider_usage_panel()"""

    def test_panel_has_correct_title(self):
        """Tests that the panel has the title 'Provider Usage Breakdown'."""
        builder = DashboardBuilder()
        panel = builder.create_provider_usage_panel()
        assert panel['title'] == 'Provider Usage Breakdown'

    def test_panel_is_piechart(self):
        """Tests that the panel type is 'piechart'."""
        builder = DashboardBuilder()
        panel = builder.create_provider_usage_panel()
        assert panel['type'] == 'piechart'

    def test_panel_uses_correct_metric(self):
        """Tests that the panel uses the sat_provider_requests_total metric."""
        builder = DashboardBuilder()
        panel = builder.create_provider_usage_panel()
        assert len(panel['targets']) == 1
        assert panel['targets'][0]['expr'] == 'sum by (provider) (sat_provider_requests_total)'

    def test_panel_groups_by_provider(self):
        """Tests that the panel is grouped by the 'provider' label."""
        builder = DashboardBuilder()
        panel = builder.create_provider_usage_panel()
        assert panel['targets'][0]['legendFormat'] == '{{provider}}'

    def test_panel_has_piechart_formatting(self):
        """Tests that the panel has proper pie chart formatting."""
        builder = DashboardBuilder()
        panel = builder.create_provider_usage_panel()
        assert panel['options']['legend']['displayMode'] == 'list'
        assert panel['fieldConfig']['defaults']['custom']['pieType'] == 'donut'

    def test_panel_is_valid_grafana_json(self):
        """Tests that the panel JSON is valid Grafana format."""
        builder = DashboardBuilder()
        panel = builder.create_provider_usage_panel()
        try:
            json.dumps(panel)
        except (TypeError, OverflowError):
            pytest.fail("The panel is not valid JSON")

    def test_with_custom_title(self):
        """Tests that custom title parameter works correctly."""
        builder = DashboardBuilder()
        panel = builder.create_provider_usage_panel(custom_title='Custom Provider Panel')
        assert panel['title'] == 'Custom Provider Panel'

    def test_with_custom_datasource(self):
        """Tests that custom datasource parameter works correctly."""
        builder = DashboardBuilder()
        panel = builder.create_provider_usage_panel(datasource='MyPrometheus')
        assert panel['datasource'] == 'MyPrometheus'

    def test_with_custom_grid_pos(self):
        """Tests that custom grid position parameter works correctly."""
        builder = DashboardBuilder()
        grid_pos = {'x': 12, 'y': 0, 'w': 12, 'h': 8}
        panel = builder.create_provider_usage_panel(grid_pos=grid_pos)
        assert panel['gridPos'] == grid_pos

    def test_with_custom_queries(self):
        """Tests that custom queries parameter works correctly."""
        builder = DashboardBuilder()
        custom_queries = [
            {'expr': 'sum by (provider) (another_metric)', 'legendFormat': '{{provider}}'}
        ]
        panel = builder.create_provider_usage_panel(queries=custom_queries)
        assert len(panel['targets']) == 1
        assert panel['targets'][0]['expr'] == 'sum by (provider) (another_metric)'

    def test_panel_has_field_config(self):
        """Tests that the panel has proper fieldConfig structure."""
        builder = DashboardBuilder()
        panel = builder.create_provider_usage_panel()
        assert 'fieldConfig' in panel
        assert 'defaults' in panel['fieldConfig']
        assert 'color' in panel['fieldConfig']['defaults']
        assert 'custom' in panel['fieldConfig']['defaults']
        assert 'displayMode' in panel['fieldConfig']['defaults']['custom']
        assert 'pieType' in panel['fieldConfig']['defaults']['custom']
        assert 'showLegend' in panel['fieldConfig']['defaults']['custom']

    def test_panel_default_options(self):
        """Tests that panel has default legend and tooltip settings."""
        builder = DashboardBuilder()
        panel = builder.create_provider_usage_panel()
        assert panel['options']['legend']['displayMode'] == 'list'
        assert panel['options']['legend']['placement'] == 'bottom'
        assert panel['options']['tooltip']['mode'] == 'single'
        assert panel['options']['tooltip']['sort'] == 'none'

    def test_panel_with_empty_queries(self):
        """Tests that panel handles empty queries list gracefully."""
        builder = DashboardBuilder()
        panel = builder.create_provider_usage_panel(queries=[])
        assert panel['targets'] == []

    def test_panel_with_special_chars_in_title(self):
        """Tests that panel handles special characters in custom title."""
        builder = DashboardBuilder()
        special_title = 'Provider Usage: Test 2024/2025 (Beta)'
        panel = builder.create_provider_usage_panel(custom_title=special_title)
        assert panel['title'] == special_title
