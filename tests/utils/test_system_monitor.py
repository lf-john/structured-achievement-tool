"""
IMPLEMENTATION PLAN for US-008:

Components:
  - src/utils/system_monitor.py:
    - get_memory_usage(): Executes 'free -h' command and parses output
    - get_cpu_load(): Executes uptime or /proc/loadavg and parses load averages

Test Cases:
  1. get_memory_usage() returns memory data with proper format
  2. get_cpu_load() returns load averages
  3. Both functions handle command failures gracefully
  4. Output parsing handles various free -h formats
  5. Output parsing handles various uptime formats

Edge Cases:
  - Command execution fails (subprocess error)
  - Empty output from commands
  - Malformed output (missing expected fields)
  - Different free -h output formats
  - Different load average formats
"""

import subprocess
from unittest.mock import MagicMock, patch

from src.utils.system_monitor import get_cpu_load, get_memory_usage


class TestMemoryUsage:
    """Tests for get_memory_usage() function"""

    @patch('subprocess.run')
    def test_get_memory_usage_returns_data_with_free_h(self, mock_run):
        """Test that get_memory_usage calls free -h and returns parsed data"""
        # Mock free -h output
        mock_run.return_value = MagicMock(
            stdout="total        used        free      shared  buff/cache   available\n"
                  "7.7Gi       4.2Gi       3.5Gi       1.1Gi       0.4Gi       5.2Gi\n"
                  "Mem:          7896       4200       3500       1100        400        5200\n"
                  "Swap:         2048          0       2048\n"
        )

        result = get_memory_usage()

        assert 'total' in result
        assert 'used' in result
        assert 'free' in result
        assert 'available' in result
        assert isinstance(result['total'], str)
        assert isinstance(result['used'], str)
        assert isinstance(result['free'], str)
        assert isinstance(result['available'], str)

    @patch('subprocess.run')
    def test_get_memory_usage_handles_free_h_failure(self, mock_run):
        """Test that get_memory_usage handles subprocess failure gracefully"""
        mock_run.side_effect = subprocess.CalledProcessError(1, 'free -h')

        result = get_memory_usage()

        assert result is None

    @patch('subprocess.run')
    def test_get_memory_usage_handles_empty_output(self, mock_run):
        """Test that get_memory_usage handles empty output gracefully"""
        mock_run.return_value = MagicMock(stdout='')

        result = get_memory_usage()

        assert result is None

    @patch('subprocess.run')
    def test_get_memory_usage_handles_malformed_output(self, mock_run):
        """Test that get_memory_usage handles malformed output gracefully"""
        mock_run.return_value = MagicMock(
            stdout="Invalid output format\n"
        )

        result = get_memory_usage()

        assert result is None


class TestCPULoad:
    """Tests for get_cpu_load() function"""

    @patch('subprocess.run')
    def test_get_cpu_load_returns_load_averages(self, mock_run):
        """Test that get_cpu_load returns load averages"""
        # Mock uptime output
        mock_run.return_value = MagicMock(
            stdout=" 12:34:56 up 45 days,  3:21,  2 users,  load average: 1.23, 1.45, 1.67"
        )

        result = get_cpu_load()

        assert result is not None
        assert 'load' in result
        assert isinstance(result['load'], (list, tuple))
        assert len(result['load']) == 3  # 1-minute, 5-minute, 15-minute averages
        assert result['load'][0] == 1.23
        assert result['load'][1] == 1.45
        assert result['load'][2] == 1.67

    @patch('subprocess.run')
    def test_get_cpu_load_handles_up_time_failure(self, mock_run):
        """Test that get_cpu_load handles uptime failure gracefully"""
        mock_run.side_effect = subprocess.CalledProcessError(1, 'uptime')

        result = get_cpu_load()

        assert result is None

    @patch('subprocess.run')
    def test_get_cpu_load_handles_empty_output(self, mock_run):
        """Test that get_cpu_load handles empty output gracefully"""
        mock_run.return_value = MagicMock(stdout='')

        result = get_cpu_load()

        assert result is None

    @patch('subprocess.run')
    def test_get_cpu_load_handles_malformed_output(self, mock_run):
        """Test that get_cpu_load handles malformed output gracefully"""
        mock_run.return_value = MagicMock(
            stdout="Invalid load format\n"
        )

        result = get_cpu_load()

        assert result is None

    @patch('subprocess.run')
    def test_get_cpu_load_handles_no_load_data(self, mock_run):
        """Test that get_cpu_load handles missing load average in output"""
        mock_run.return_value = MagicMock(
            stdout="12:34:56 up 45 days,  3:21,  2 users"
        )

        result = get_cpu_load()

        assert result is None


class TestIntegration:
    """Integration tests for combined system monitoring"""

    @patch('subprocess.run')
    def test_get_system_metrics_returns_both_memory_and_cpu(self, mock_run):
        """Test that combined system monitoring works correctly"""
        mock_run.side_effect = [
            MagicMock(
                stdout="total        used        free      shared  buff/cache   available\n"
                      "Mem:          7.7Gi       4.2Gi       3.5Gi       1.1Gi       0.4Gi       5.2Gi\n"
            ),
            MagicMock(
                stdout=" 12:34:56 up 45 days,  3:21,  2 users,  load average: 1.23, 1.45, 1.67"
            )
        ]

        result = get_memory_usage()
        cpu_result = get_cpu_load()

        assert result is not None
        assert cpu_result is not None
        assert 'load' in cpu_result
        assert 'total' in result
        assert 'used' in result
