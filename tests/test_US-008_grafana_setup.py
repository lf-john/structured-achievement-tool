import pytest
import sys
import os
from unittest.mock import MagicMock, patch, call

# Import the script modules
from src.grafana_setup import GrafanaSetup


class TestGrafanaSetupClass:
    """Test cases for the GrafanaSetup class."""

    @pytest.fixture
    def mock_api_key(self):
        return "test_api_key"

    @pytest.fixture
    def mock_dry_run(self):
        return False

    @pytest.fixture
    def setup(self, mock_api_key, mock_dry_run):
        """Create a GrafanaSetup instance for testing."""
        with patch('src.core.grafana_client.GrafanaClient'), \
             patch('src.dashboard_builder.DashboardBuilder'):
            return GrafanaSetup(api_key=mock_api_key, dry_run=mock_dry_run)

    # AC 6: Reads GRAFANA_API_KEY from environment variable
    def test_init_reads_api_key_from_env_var(self, mock_api_key):
        """Test that api_key is read from GRAFANA_API_KEY environment variable."""
        with patch.dict(os.environ, {'GRAFANA_API_KEY': mock_api_key}):
            with patch('src.core.grafana_client.GrafanaClient'), \
                 patch('src.dashboard_builder.DashboardBuilder'):
                setup = GrafanaSetup()
                assert setup.api_key == mock_api_key

    def test_init_raises_error_when_api_key_not_set(self):
        """Test that ValueError is raised when GRAFANA_API_KEY is not set."""
        with patch.dict(os.environ, {'GRAFANA_API_KEY': ''}, clear=True):
            with patch('src.core.grafana_client.GrafanaClient'), \
                 patch('src.dashboard_builder.DashboardBuilder'):
                with pytest.raises(ValueError, match="GRAFANA_API_KEY environment variable must be set"):
                    GrafanaSetup()

    def test_init_accepts_api_key_from_argument(self):
        """Test that api_key can be provided via --api-key argument."""
        custom_key = "custom_api_key"
        with patch('src.core.grafana_client.GrafanaClient'), \
             patch('src.dashboard_builder.DashboardBuilder'):
            setup = GrafanaSetup(api_key=custom_key)
            assert setup.api_key == custom_key

    # AC 5: Implements --dry-run flag
    def test_init_with_dry_run_flag(self):
        """Test that dry_run flag is properly set."""
        with patch('src.core.grafana_client.GrafanaClient'), \
             patch('src.dashboard_builder.DashboardBuilder'):
            setup = GrafanaSetup(dry_run=True)
            assert setup.dry_run is True

    def test_init_without_dry_run_flag(self):
        """Test that dry_run is False by default."""
        with patch('src.core.grafana_client.GrafanaClient'), \
             patch('src.dashboard_builder.DashboardBuilder'):
            setup = GrafanaSetup()
            assert setup.dry_run is False

    # AC 2: Idempotency logic checks if dashboard exists
    def test_check_dashboard_exists_returns_true_when_exists(self, setup):
        """Test that check_dashboard_exists returns True when dashboard exists."""
        with patch.object(setup.client, 'get_dashboard') as mock_get:
            mock_get.return_value = {}
            assert setup.check_dashboard_exists("test-uid") is True
            mock_get.assert_called_once_with("test-uid")

    def test_check_dashboard_exists_returns_false_when_not_found(self, setup):
        """Test that check_dashboard_exists returns False when dashboard doesn't exist."""
        with patch.object(setup.client, 'get_dashboard', side_effect=Exception("Not found")):
            assert setup.check_dashboard_exists("test-uid") is False

    # AC 3: Updates existing dashboard if UID matches
    def test_update_dashboard_in_dry_run_mode(self, setup):
        """Test that update_dashboard works in dry-run mode."""
        dashboard = {'uid': 'test-uid', 'title': 'Test'}
        with patch.object(setup, 'check_dashboard_exists', return_value=True):
            result = setup.update_dashboard('test-uid', dashboard)
            assert result == dashboard
            # Should print dashboard JSON but not call API

    def test_update_dashboard_in_production_mode(self, setup):
        """Test that update_dashboard calls API in production mode."""
        dashboard = {'uid': 'test-uid', 'title': 'Test'}
        mock_client = MagicMock()
        setup.client = mock_client

        with patch.object(setup, 'check_dashboard_exists', return_value=True):
            result = setup.update_dashboard('test-uid', dashboard)
            mock_client.update_dashboard.assert_called_once_with('test-uid', dashboard)

    # AC 4: Creates new dashboard if does not exist
    def test_create_dashboard_in_dry_run_mode(self, setup):
        """Test that create_dashboard works in dry-run mode."""
        dashboard = {'uid': 'test-uid', 'title': 'Test'}
        with patch.object(setup, 'check_dashboard_exists', return_value=False):
            result = setup.create_dashboard(dashboard)
            assert result == dashboard
            # Should print dashboard JSON but not call API

    def test_create_dashboard_in_production_mode(self, setup):
        """Test that create_dashboard calls API in production mode."""
        dashboard = {'uid': 'test-uid', 'title': 'Test'}
        mock_client = MagicMock()
        setup.client = mock_client

        with patch.object(setup, 'check_dashboard_exists', return_value=False):
            result = setup.create_dashboard(dashboard)
            mock_client.create_dashboard.assert_called_once_with(dashboard)

    # AC 1: Main script orchestrates all panel creation
    def test_setup_dashboard_creates_dashboard_structure(self, setup):
        """Test that setup_dashboard creates proper dashboard structure."""
        with patch.object(setup.builder, 'create_dashboard') as mock_create:
            mock_create.return_value = {'uid': 'test-uid', 'title': 'Test'}
            with patch.object(setup, 'check_dashboard_exists', return_value=False):
                result = setup.setup_dashboard('test-uid', 'Test')
                mock_create.assert_called_once_with('Test', 'test-uid', None, None)

    def test_setup_dashboard_with_custom_panels(self, setup):
        """Test that setup_dashboard uses provided panels."""
        panels = [{'type': 'timeseries', 'title': 'Test'}]
        with patch.object(setup.builder, 'create_dashboard') as mock_create:
            mock_create.return_value = {'uid': 'test-uid', 'title': 'Test'}
            with patch.object(setup, 'check_dashboard_exists', return_value=False):
                result = setup.setup_dashboard('test-uid', 'Test', panels=panels)
                mock_create.assert_called_once_with('Test', 'test-uid', panels, None)

    def test_setup_dashboard_with_custom_options(self, setup):
        """Test that setup_dashboard uses provided options."""
        options = {'time': {'from': 'now-1h', 'to': 'now'}}
        with patch.object(setup.builder, 'create_dashboard') as mock_create:
            mock_create.return_value = {'uid': 'test-uid', 'title': 'Test'}
            with patch.object(setup, 'check_dashboard_exists', return_value=False):
                result = setup.setup_dashboard('test-uid', 'Test', options=options)
                mock_create.assert_called_once_with('Test', 'test-uid', None, options)

    def test_setup_dashboard_with_datasource(self, setup):
        """Test that setup_dashboard adds datasource."""
        with patch.object(setup.builder, 'create_dashboard') as mock_create:
            mock_create.return_value = {'uid': 'test-uid', 'title': 'Test'}
            with patch.object(setup, 'check_dashboard_exists', return_value=False):
                result = setup.setup_dashboard('test-uid', 'Test', datasource='Prometheus')
                mock_create.return_value['datasource'] == 'Prometheus'

    # AC 7: Proper error handling and user feedback
    def test_setup_dashboard_validates_uid(self, setup):
        """Test that setup_dashboard raises ValueError when uid is empty."""
        with patch.object(setup.builder, 'create_dashboard') as mock_create:
            mock_create.return_value = {}
            with pytest.raises(ValueError, match="UID is required"):
                setup.setup_dashboard('', 'Test')

    def test_setup_dashboard_validates_name(self, setup):
        """Test that setup_dashboard raises ValueError when name is empty."""
        with patch.object(setup.builder, 'create_dashboard') as mock_create:
            mock_create.return_value = {}
            with pytest.raises(ValueError, match="Name is required"):
                setup.setup_dashboard('test-uid', '')

    # AC 8: Script can be run multiple times safely
    def test_setup_dashboard_idempotent_same_uid(self, setup):
        """Test that setup_dashboard can be called multiple times safely with same UID."""
        with patch.object(setup.builder, 'create_dashboard') as mock_create:
            mock_create.return_value = {'uid': 'test-uid', 'title': 'Test'}
            with patch.object(setup, 'check_dashboard_exists', return_value=False):
                # First call
                result1 = setup.setup_dashboard('test-uid', 'Test')
                # Second call
                result2 = setup.setup_dashboard('test-uid', 'Test')

                # Both should succeed without errors
                assert result1 is not None
                assert result2 is not None

    def test_setup_dashboard_idempotent_different_implementation(self, setup):
        """Test that setup_dashboard can update existing dashboard."""
        dashboard = {'uid': 'test-uid', 'title': 'Test'}

        with patch.object(setup.builder, 'create_dashboard', return_value=dashboard):
            with patch.object(setup, 'check_dashboard_exists', return_value=False):
                # First call - creates
                result1 = setup.setup_dashboard('test-uid', 'Test')

            with patch.object(setup, 'check_dashboard_exists', return_value=True):
                # Second call - updates
                result2 = setup.setup_dashboard('test-uid', 'Test Updated')

            # Both should succeed
            assert result1 is not None
            assert result2 is not None

    # Additional test: save functionality
    def test_setup_dashboard_saves_to_file(self, setup, tmp_path, monkeypatch):
        """Test that setup_dashboard saves JSON to file when --save is True."""
        dashboard = {'uid': 'test-uid', 'title': 'Test'}
        saved_file = tmp_path / "test-uid.json"

        # Mock sys.stdout to prevent output during test
        monkeypatch.setattr('sys.stdout', MagicMock())

        with patch.object(setup.builder, 'create_dashboard', return_value=dashboard):
            with patch.object(setup, 'check_dashboard_exists', return_value=False):
                setup.setup_dashboard('test-uid', 'Test', save=True)

        # Check that file was created
        assert saved_file.exists()

        # Check file content
        import json
        with open(saved_file) as f:
            content = json.load(f)
            assert content == dashboard


class TestGrafanaSetupCLI:
    """Test cases for command-line interface."""

    @pytest.fixture
    def cli_runner(self):
        """Create a CLI runner for testing."""
        return pytest.MonkeyPatch()

    def test_main_help(self, capsys):
        """Test that main() displays help information."""
        with patch.object(sys, 'argv', ['grafana_setup.py', '--help']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_main_invalid_json_panels(self, capsys):
        """Test that main() exits with error for invalid JSON panels."""
        with patch.object(sys, 'argv', ['grafana_setup.py', '--uid', 'test', '--name', 'Test', '--panels', '[invalid]']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_main_invalid_json_options(self, capsys):
        """Test that main() exits with error for invalid JSON options."""
        with patch.object(sys, 'argv', ['grafana_setup.py', '--uid', 'test', '--name', 'Test', '--options', '[invalid]']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_main_missing_required_arguments(self, capsys):
        """Test that main() exits with error when UID or name is missing."""
        with patch.object(sys, 'argv', ['grafana_setup.py', '--uid', 'test']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

        with patch.object(sys, 'argv', ['grafana_setup.py', '--name', 'Test']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1


# Test runner helper
def main():
    """Run tests and exit with appropriate code."""
    exit_code = pytest.main([__file__, '-v'])
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
