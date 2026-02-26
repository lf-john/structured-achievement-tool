"""
IMPLEMENTATION PLAN for US-007:

Components:
  - check_prometheus_targets(): Function that queries http://localhost:9090/api/v1/targets
    and returns target health information including:
      - List of active targets
      - List of health statuses (up, down)
      - Number of targets in each health state

Test Cases:
  1. AC: Prometheus targets are checked and reported -> test_returns_target_data_on_success
  2. AC: Returns proper structure with activeTargets -> test_active_targets_in_response
  3. Edge case: Returns up status for healthy targets -> test_returns_up_for_healthy_targets
  4. Edge case: Returns down status for unhealthy targets -> test_returns_down_for_unhealthy_targets
  5. Edge case: Handles missing activeTargets key -> test_handles_missing_active_targets
  6. Edge case: Handles empty targets list -> test_handles_empty_targets_list
  7. Negative case: Handles network errors -> test_handles_network_error
  8. Negative case: Handles invalid JSON response -> test_handles_invalid_json_response

Edge Cases:
  - Multiple targets with mixed health statuses
  - No active targets available
  - Request timeout
  - Connection refused
  - Non-200 HTTP status codes
"""

import pytest
import sys
from unittest.mock import patch, MagicMock, mock_open
from io import StringIO

# Expected imports will fail initially (TDD-RED state)
from src.health_check import check_prometheus_targets


class TestPrometheusTargetsCollection:
    """Tests for US-007: Collect Prometheus Target Health Metrics"""

    @patch("src.health_check.requests.get")
    def test_returns_target_data_on_success(self, mock_get):
        """Test that function returns target data when Prometheus is healthy"""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "data": {
                "activeTargets": [
                    {
                        "scrapePool": "prometheus",
                        "scrapeUrl": "http://localhost:9090/metrics",
                        "health": "up"
                    },
                    {
                        "scrapePool": "node_exporter",
                        "scrapeUrl": "http://localhost:9100/metrics",
                        "health": "up"
                    }
                ]
            }
        }
        mock_get.return_value = mock_response

        result = check_prometheus_targets()

        # Should return the parsed JSON
        assert isinstance(result, dict)
        assert "status" in result
        assert "data" in result
        assert "activeTargets" in result["data"]
        assert len(result["data"]["activeTargets"]) == 2

    @patch("src.health_check.requests.get")
    def test_active_targets_in_response(self, mock_get):
        """Test that response contains properly structured activeTargets"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "data": {
                "activeTargets": [
                    {
                        "scrapePool": "prometheus",
                        "scrapeUrl": "http://localhost:9090/metrics",
                        "health": "up"
                    }
                ]
            }
        }
        mock_get.return_value = mock_response

        result = check_prometheus_targets()

        assert result["status"] == "success"
        assert result["data"]["activeTargets"] == [
            {
                "scrapePool": "prometheus",
                "scrapeUrl": "http://localhost:9090/metrics",
                "health": "up"
            }
        ]

    @patch("src.health_check.requests.get")
    def test_returns_up_for_healthy_targets(self, mock_get):
        """Test that healthy targets are reported with 'up' status"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "data": {
                "activeTargets": [
                    {
                        "scrapePool": "prometheus",
                        "scrapeUrl": "http://localhost:9090/metrics",
                        "health": "up"
                    }
                ]
            }
        }
        mock_get.return_value = mock_response

        result = check_prometheus_targets()

        targets = result["data"]["activeTargets"]
        assert len(targets) == 1
        assert targets[0]["health"] == "up"
        assert targets[0]["scrapePool"] == "prometheus"

    @patch("src.health_check.requests.get")
    def test_returns_down_for_unhealthy_targets(self, mock_get):
        """Test that unhealthy targets are reported with 'down' status"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "data": {
                "activeTargets": [
                    {
                        "scrapePool": "prometheus",
                        "scrapeUrl": "http://localhost:9090/metrics",
                        "health": "down"
                    }
                ]
            }
        }
        mock_get.return_value = mock_response

        result = check_prometheus_targets()

        targets = result["data"]["activeTargets"]
        assert len(targets) == 1
        assert targets[0]["health"] == "down"

    @patch("src.health_check.requests.get")
    def test_handles_missing_active_targets(self, mock_get):
        """Test that function handles missing activeTargets key gracefully"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "data": {}
        }
        mock_get.return_value = mock_response

        result = check_prometheus_targets()

        # Should return empty list or handle gracefully
        assert result["status"] == "success"
        assert "activeTargets" in result["data"]
        assert result["data"]["activeTargets"] == []

    @patch("src.health_check.requests.get")
    def test_handles_empty_targets_list(self, mock_get):
        """Test that function handles empty targets list"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "data": {
                "activeTargets": []
            }
        }
        mock_get.return_value = mock_response

        result = check_prometheus_targets()

        assert result["status"] == "success"
        assert result["data"]["activeTargets"] == []

    @patch("src.health_check.requests.get")
    def test_handles_network_error(self, mock_get):
        """Test that function handles network errors gracefully"""
        mock_get.side_effect = ConnectionError("Connection refused")

        result = check_prometheus_targets()

        # Should handle error and return appropriate message
        assert isinstance(result, str) or isinstance(result, dict)
        # Function should return an error indicator

    @patch("src.health_check.requests.get")
    def test_handles_invalid_json_response(self, mock_get):
        """Test that function handles invalid JSON response"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_get.return_value = mock_response

        result = check_prometheus_targets()

        # Should handle invalid JSON and return error indicator

    @patch("src.health_check.requests.get")
    def test_handles_non_200_status_code(self, mock_get):
        """Test that function handles non-200 status codes"""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = check_prometheus_targets()

        # Should handle error status and return appropriate message


class TestPrometheusTargetsIntegration:
    """Integration tests for Prometheus target collection"""

    @patch("src.health_check.requests.get")
    def test_multiple_targets_with_mixed_health(self, mock_get):
        """Test collection of multiple targets with mixed health statuses"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "data": {
                "activeTargets": [
                    {
                        "scrapePool": "prometheus",
                        "scrapeUrl": "http://localhost:9090/metrics",
                        "health": "up"
                    },
                    {
                        "scrapePool": "node_exporter",
                        "scrapeUrl": "http://localhost:9100/metrics",
                        "health": "down"
                    },
                    {
                        "scrapePool": "alertmanager",
                        "scrapeUrl": "http://localhost:9093/metrics",
                        "health": "up"
                    }
                ]
            }
        }
        mock_get.return_value = mock_response

        result = check_prometheus_targets()

        targets = result["data"]["activeTargets"]
        assert len(targets) == 3

        up_count = sum(1 for t in targets if t["health"] == "up")
        down_count = sum(1 for t in targets if t["health"] == "down")

        assert up_count == 2
        assert down_count == 1

    @patch("src.health_check.requests.get")
    def test_target_structure_validation(self, mock_get):
        """Test that target objects have required fields"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "data": {
                "activeTargets": [
                    {
                        "scrapePool": "test_pool",
                        "scrapeUrl": "http://test:9090/metrics",
                        "health": "up"
                    }
                ]
            }
        }
        mock_get.return_value = mock_response

        result = check_prometheus_targets()

        targets = result["data"]["activeTargets"]
        target = targets[0]

        # Verify required fields exist
        assert "scrapePool" in target
        assert "scrapeUrl" in target
        assert "health" in target

        # Verify field types/values
        assert isinstance(target["scrapePool"], str)
        assert isinstance(target["scrapeUrl"], str)
        assert isinstance(target["health"], str)


if __name__ == "__main__":
    # Run tests with custom exit code
    fail_count = 0
    test_runner = TestPrometheusTargetsCollection()

    tests = [
        ("test_returns_target_data_on_success", test_runner.test_returns_target_data_on_success),
        ("test_active_targets_in_response", test_runner.test_active_targets_in_response),
        ("test_returns_up_for_healthy_targets", test_runner.test_returns_up_for_healthy_targets),
        ("test_returns_down_for_unhealthy_targets", test_runner.test_returns_down_for_unhealthy_targets),
        ("test_handles_missing_active_targets", test_runner.test_handles_missing_active_targets),
        ("test_handles_empty_targets_list", test_runner.test_handles_empty_targets_list),
        ("test_handles_network_error", test_runner.test_handles_network_error),
        ("test_handles_invalid_json_response", test_runner.test_handles_invalid_json_response),
        ("test_handles_non_200_status_code", test_runner.test_handles_non_200_status_code),
    ]

    test_runner2 = TestPrometheusTargetsIntegration()
    tests.extend([
        ("test_multiple_targets_with_mixed_health", test_runner2.test_multiple_targets_with_mixed_health),
        ("test_target_structure_validation", test_runner2.test_target_structure_validation),
    ])

    for test_name, test_func in tests:
        try:
            test_func()
            print(f"✓ {test_name}")
        except AssertionError as e:
            print(f"✗ {test_name}: {e}")
            fail_count += 1
        except Exception as e:
            print(f"✗ {test_name}: Unexpected error: {e}")
            fail_count += 1

    print(f"\n{fail_count}/{len(tests)} tests failed")
    sys.exit(1 if fail_count > 0 else 0)
