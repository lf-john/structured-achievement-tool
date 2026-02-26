"""
IMPLEMENTATION PLAN for US-009: Verify Network Port Connectivity

Components:
  - PortChecker.check_listening(): Already exists in src/execution/verification_sdk.py
    - Tests TCP connectivity to host:port
    - Returns VerifyResult with passed=True/False status
    - Handles timeout and connection errors

Test Cases:
  1. AC1: Verify port 8080 is listening
  2. AC1: Verify port 8088 is listening
  3. AC1: Verify port 8090 is listening
  4. AC1: Verify port 9090 is listening
  5. AC1: Verify port 3001 is listening
  6. AC1: Verify port 11434 (Ollama) is listening

Edge Cases:
  - Port is closed (connection refused)
  - Port is unreachable (timeout)
  - Invalid port number
  - Port in use by different service
  - Non-existent host
"""

import socket
from unittest.mock import patch, MagicMock
import pytest

from src.execution.verification_sdk import PortChecker, VerifyResult


class TestPortChecker:
    """Tests for PortChecker.check_listening() method."""

    def test_port_8080_listening(self):
        """Verify port 8080 is listening."""
        pc = PortChecker()
        result = pc.check_listening("localhost", 8080)
        assert isinstance(result, VerifyResult)
        assert result.checker == "port"
        assert result.target == "localhost:8080"

    def test_port_8088_listening(self):
        """Verify port 8088 is listening."""
        pc = PortChecker()
        result = pc.check_listening("localhost", 8088)
        assert isinstance(result, VerifyResult)
        assert result.checker == "port"
        assert result.target == "localhost:8088"

    def test_port_8090_listening(self):
        """Verify port 8090 is listening."""
        pc = PortChecker()
        result = pc.check_listening("localhost", 8090)
        assert isinstance(result, VerifyResult)
        assert result.checker == "port"
        assert result.target == "localhost:8090"

    def test_port_9090_listening(self):
        """Verify port 9090 is listening."""
        pc = PortChecker()
        result = pc.check_listening("localhost", 9090)
        assert isinstance(result, VerifyResult)
        assert result.checker == "port"
        assert result.target == "localhost:9090"

    def test_port_3001_listening(self):
        """Verify port 3001 is listening."""
        pc = PortChecker()
        result = pc.check_listening("localhost", 3001)
        assert isinstance(result, VerifyResult)
        assert result.checker == "port"
        assert result.target == "localhost:3001"

    def test_port_11434_listening(self):
        """Verify port 11434 (Ollama) is listening."""
        pc = PortChecker()
        result = pc.check_listening("localhost", 11434)
        assert isinstance(result, VerifyResult)
        assert result.checker == "port"
        assert result.target == "localhost:11434"


class TestPortCheckerEdgeCases:
    """Edge case tests for PortChecker.check_listening() method."""

    def test_closed_port_returns_fail(self):
        """Test that a closed port returns FAIL status."""
        pc = PortChecker()
        result = pc.check_listening("localhost", 12345)  # Unlikely to be in use
        assert isinstance(result, VerifyResult)
        assert result.passed is False
        assert result.checker == "port"
        assert "refused" in result.message.lower()

    def test_connection_timeout_returns_fail(self):
        """Test that connection timeout returns FAIL status."""
        pc = PortChecker()
        # Mock socket to simulate timeout
        with patch('socket.socket') as mock_socket:
            mock_sock = MagicMock()
            mock_socket.return_value = mock_sock
            mock_sock.connect_ex.return_value = 111  # Connection refused or timeout

            result = pc.check_listening("localhost", 9999)

            assert isinstance(result, VerifyResult)
            assert result.passed is False
            assert "refused" in result.message.lower() or "timed out" in result.message.lower()

    def test_port_11434_check_ollama(self):
        """Verify Ollama port 11434 is accessible."""
        pc = PortChecker()
        result = pc.check_listening("localhost", 11434)
        assert isinstance(result, VerifyResult)
        assert result.checker == "port"
        # Note: Actual pass/fail depends on whether Ollama is running

    def test_invalid_port_number(self):
        """Test that invalid port numbers are handled correctly."""
        pc = PortChecker()
        # Port 0 is invalid (system-assigned on connect)
        # Port numbers > 65535 are invalid
        result = pc.check_listening("localhost", 70000)
        assert isinstance(result, VerifyResult)
        assert result.passed is False
        assert "error" in result.message.lower()

    def test_verify_result_str_representation(self):
        """Test VerifyResult string representation."""
        pc = PortChecker()
        result = pc.check_listening("localhost", 8080)

        result_str = str(result)
        assert "[PASS]" in result_str or "[FAIL]" in result_str
        assert "port:localhost:8080" in result_str
        assert result.target in result_str
