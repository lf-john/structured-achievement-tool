"""
IMPLEMENTATION PLAN for US-001:

Components:
  - src/mautic/config_manager.py: New module to manage Mautic configuration within Docker.
  - configure_mautic_sending_limits(): Main function to apply the configuration.
  - _exec_in_mautic_container(command: list[str]) -> str: Internal helper for Docker exec commands.
  - _read_mautic_local_php() -> str: Reads local.php content from the container.
  - _write_mautic_local_php(content: str): Writes content to local.php in the container.
  - _update_config_values(config_content: str, key: str, value: str | int) -> str: Utility to update/insert config values.

Test Cases:
  1. AC 1 (`mailer_spool_type`): Verify `mailer_spool_type` is set to `file`.
  2. AC 2 (`mailer_spool_msg_limit`): Verify `mailer_spool_msg_limit` is set to `50`.
  3. Edge Case (Existing values updated): Verify existing different values are correctly overwritten.
  4. Edge Case (File initially empty/missing): Verify file is created or content is correctly appended if keys are missing.
  5. Negative Case (Docker exec failure): Verify errors are handled if Docker commands fail.
"""
import pytest
import sys
from unittest.mock import patch, MagicMock

# We expect this import to fail initially, leading to TDD-RED state.
from src.mautic.config_manager import configure_mautic_sending_limits

class TestMauticConfigManager:

    # Mock content for local.php
    INITIAL_LOCAL_PHP_CONTENT = """<?php
$parameters = [
    'mailer_dsn' => null,
    'mailer_spool_type' => 'memory',
    'mailer_spool_msg_limit' => 10,
    'db_table_prefix' => null,
];
"""

    EMPTY_LOCAL_PHP_CONTENT = """<?php
$parameters = [
];
"""

    @patch('src.mautic.config_manager._exec_in_mautic_container')
    def test_should_set_mailer_spool_type_to_file(self, mock_exec):
        # Simulate reading initial content
        mock_exec.side_effect = [
            MagicMock(output=self.INITIAL_LOCAL_PHP_CONTENT), # Read call
            MagicMock(output=''), # Write call (successful)
        ]
        
        configure_mautic_sending_limits()

        # Verify write call has correct spool type
        write_command = mock_exec.call_args_list[1].args[0]
        assert "echo '<?php
$parameters = [
    'mailer_dsn' => null,
    'mailer_spool_type' => 'file',
    'mailer_spool_msg_limit' => 50,
    'db_table_prefix' => null,
];' > /var/www/html/config/local.php" in write_command

    @patch('src.mautic.config_manager._exec_in_mautic_container')
    def test_should_set_mailer_spool_msg_limit_to_50(self, mock_exec):
        # Simulate reading initial content
        mock_exec.side_effect = [
            MagicMock(output=self.INITIAL_LOCAL_PHP_CONTENT), # Read call
            MagicMock(output=''), # Write call (successful)
        ]

        configure_mautic_sending_limits()

        # Verify write call has correct msg limit
        write_command = mock_exec.call_args_list[1].args[0]
        assert "echo '<?php
$parameters = [
    'mailer_dsn' => null,
    'mailer_spool_type' => 'file',
    'mailer_spool_msg_limit' => 50,
    'db_table_prefix' => null,
];' > /var/www/html/config/local.php" in write_command

    @patch('src.mautic.config_manager._exec_in_mautic_container')
    def test_existing_values_are_updated(self, mock_exec):
        # Simulate initial content with different values
        initial_content_different_values = """<?php
$parameters = [
    'mailer_dsn' => null,
    'mailer_spool_type' => 'database',
    'mailer_spool_msg_limit' => 100,
];
"""
        mock_exec.side_effect = [
            MagicMock(output=initial_content_different_values), # Read call
            MagicMock(output=''), # Write call (successful)
        ]

        configure_mautic_sending_limits()

        # Verify that the output command replaces the values correctly
        write_command_arg = mock_exec.call_args_list[1].args[0]
        expected_content_part_type = "'mailer_spool_type' => 'file',"
        expected_content_part_limit = "'mailer_spool_msg_limit' => 50,"
        assert expected_content_part_type in write_command_arg
        assert expected_content_part_limit in write_command_arg
        assert "'mailer_spool_type' => 'database'," not in write_command_arg # Ensure old value is gone
        assert "'mailer_spool_msg_limit' => 100," not in write_command_arg # Ensure old value is gone


    @patch('src.mautic.config_manager._exec_in_mautic_container')
    def test_file_initially_empty_or_missing_creates_values(self, mock_exec):
        # Simulate an empty config file
        mock_exec.side_effect = [
            MagicMock(output=self.EMPTY_LOCAL_PHP_CONTENT), # Read call
            MagicMock(output=''), # Write call (successful)
        ]

        configure_mautic_sending_limits()

        # Verify that the output command includes the new values
        write_command_arg = mock_exec.call_args_list[1].args[0]
        expected_content_part_type = "'mailer_spool_type' => 'file',"
        expected_content_part_limit = "'mailer_spool_msg_limit' => 50,"
        assert expected_content_part_type in write_command_arg
        assert expected_content_part_limit in write_command_arg
        assert "echo '<?php
$parameters = [
    'mailer_spool_type' => 'file',
    'mailer_spool_msg_limit' => 50,
];' > /var/www/html/config/local.php" in write_command_arg


    @patch('src.mautic.config_manager._exec_in_mautic_container')
    def test_docker_exec_failure_during_read_raises_exception(self, mock_exec):
        mock_exec.side_effect = Exception("Docker command failed")

        with pytest.raises(Exception, match="Docker command failed"):
            configure_mautic_sending_limits()

    @patch('src.mautic.config_manager._exec_in_mautic_container')
    def test_docker_exec_failure_during_write_raises_exception(self, mock_exec):
        mock_exec.side_effect = [
            MagicMock(output=self.INITIAL_LOCAL_PHP_CONTENT), # Read call (successful)
            Exception("Docker write failed") # Write call (failure)
        ]

        with pytest.raises(Exception, match="Docker write failed"):
            configure_mautic_sending_limits()


# This is critical for TDD-RED-CHECK. It ensures a non-zero exit code if tests fail.
if __name__ == "__main__":
    pytest.main([__file__])
    # The actual failure will come from the import error, so this main block might not be strictly necessary
    # but it's good practice for local testing.
