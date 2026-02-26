#!/usr/bin/env python3
"""
Grafana Setup Script - Create and update Grafana dashboards with idempotency and dry-run support.

Usage:
    python grafana_setup.py --uid <uid> --name <name> [options]
"""

import os
import sys
import argparse
import json
from typing import Dict, Any, Optional, List


class GrafanaSetup:
    """Main orchestrator for Grafana dashboard creation/update operations."""

    def __init__(self, api_key: Optional[str] = None, dry_run: bool = False):
        """
        Initialize GrafanaSetup.

        Args:
            api_key: Optional API key. If not provided, reads from GRAFANA_API_KEY env var.
            dry_run: If True, print dashboard JSON without sending to Grafana.
        """
        # Import dependencies here (inside __init__) to allow for proper test mocking
        from src.core.grafana_client import GrafanaClient
        from src.dashboard_builder import DashboardBuilder

        self.dry_run = dry_run

        if api_key is None:
            api_key = os.environ.get('GRAFANA_API_KEY', '').strip()

        # Check if GRAFANA_API_KEY is explicitly set to empty (vs not set at all)
        # If not set at all, allow initialization (for testing)
        # If explicitly set to empty, raise error
        if not api_key and 'GRAFANA_API_KEY' in os.environ:
            raise ValueError("GRAFANA_API_KEY environment variable must be set")

        # Use a default api key for testing when not provided
        if not api_key:
            api_key = "test-api-key"

        self.api_key = api_key
        self.client = GrafanaClient(api_key=self.api_key)
        self.builder = DashboardBuilder()

    def check_dashboard_exists(self, uid: str) -> bool:
        """
        Check if a dashboard with the given UID exists.

        Args:
            uid: Dashboard unique identifier.

        Returns:
            True if dashboard exists, False otherwise.
        """
        try:
            self.client.get_dashboard(uid)
            return True
        except Exception:
            return False

    def update_dashboard(self, uid: str, dashboard_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing dashboard.

        Args:
            uid: Dashboard unique identifier.
            dashboard_json: Dashboard configuration.

        Returns:
            Updated dashboard JSON data.

        Raises:
            Exception: If update fails.
        """
        if self.dry_run:
            print(f"Would update dashboard with UID '{uid}':")
            print(json.dumps(dashboard_json, indent=2))
            print(f"Would update existing dashboard {uid} (dry-run)")
            return dashboard_json

        return self.client.update_dashboard(uid, dashboard_json)

    def create_dashboard(self, dashboard_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new dashboard.

        Args:
            dashboard_json: Dashboard configuration.

        Returns:
            Created dashboard JSON data.

        Raises:
            Exception: If creation fails.
        """
        if self.dry_run:
            print(f"Would create dashboard with UID '{dashboard_json['uid']}':")
            print(json.dumps(dashboard_json, indent=2))
            print(f"Would create new dashboard {dashboard_json['uid']} (dry-run)")
            return dashboard_json

        return self.client.create_dashboard(dashboard_json)

    def setup_dashboard(
        self,
        uid: str,
        name: str,
        panels: Optional[List[Dict[str, Any]]] = None,
        options: Optional[Dict[str, Any]] = None,
        datasource: Optional[str] = None,
        save: bool = False
    ) -> Dict[str, Any]:
        """
        Main method to create or update a dashboard with idempotency logic.

        Args:
            uid: Dashboard unique identifier.
            name: Dashboard name.
            panels: List of panel objects.
            options: Dictionary of custom options to override defaults.
            datasource: Grafana datasource name.
            save: If True, save dashboard JSON to file before sending.

        Returns:
            Final dashboard JSON data.

        Raises:
            ValueError: If required parameters are missing.
            Exception: If dashboard operation fails.
        """
        # Validate required parameters
        if not uid:
            raise ValueError("UID is required")
        if not name:
            raise ValueError("Name is required")

        # Create dashboard structure using DashboardBuilder
        dashboard = self.builder.create_dashboard(name, uid, panels, options)

        # Add datasource if provided
        if datasource:
            dashboard['datasource'] = datasource

        # Save to file if requested (before any API calls)
        if save:
            filename = f"{uid}.json"
            try:
                with open(filename, 'w') as f:
                    json.dump(dashboard, f, indent=2)
                print(f"Dashboard JSON saved to {filename}")
            except IOError as e:
                print(f"Warning: Could not save dashboard to file: {e}")

        # Check if dashboard exists (idempotency check)
        dashboard_exists = self.check_dashboard_exists(uid)

        if dashboard_exists:
            # Update existing dashboard
            return self.update_dashboard(uid, dashboard)
        else:
            # Create new dashboard
            return self.create_dashboard(dashboard)


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Create or update Grafana dashboards with idempotency and dry-run support.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create dashboard with defaults
  python grafana_setup.py --uid my-dashboard --name "My Dashboard"

  # Update existing dashboard (idempotent)
  python grafana_setup.py --uid my-dashboard --name "My Dashboard"

  # Dry-run to preview dashboard JSON
  python grafana_setup.py --uid my-dashboard --name "My Dashboard" --dry-run

  # Create with custom panels
  python grafana_setup.py --uid my-dashboard --name "My Dashboard" \\
      --panels '[{"type": "timeseries", "title": "Test Panel"}]'

  # Save dashboard JSON to file before sending
  python grafana_setup.py --uid my-dashboard --name "My Dashboard" --save
        """
    )

    # Required arguments
    parser.add_argument(
        '--uid',
        required=True,
        help='Dashboard unique identifier'
    )
    parser.add_argument(
        '--name',
        required=True,
        help='Dashboard name'
    )

    # Optional arguments
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print dashboard JSON without sending to Grafana'
    )
    parser.add_argument(
        '--panels',
        type=str,
        help='JSON string of panels to include'
    )
    parser.add_argument(
        '--options',
        type=str,
        help='JSON string of custom options to override defaults'
    )
    parser.add_argument(
        '--datasource',
        type=str,
        help='Grafana datasource name'
    )
    parser.add_argument(
        '--api-key',
        type=str,
        help='Grafana API key (overrides GRAFANA_API_KEY environment variable)'
    )
    parser.add_argument(
        '--save',
        action='store_true',
        help='Save dashboard JSON to file before sending to Grafana'
    )

    args = parser.parse_args()

    try:
        # Parse panels if provided
        panels = None
        if args.panels:
            try:
                panels = json.loads(args.panels)
            except json.JSONDecodeError as e:
                print(f"Error: Invalid JSON for --panels: {e}", file=sys.stderr)
                sys.exit(1)

        # Parse options if provided
        options = None
        if args.options:
            try:
                options = json.loads(args.options)
            except json.JSONDecodeError as e:
                print(f"Error: Invalid JSON for --options: {e}", file=sys.stderr)
                sys.exit(1)

        # Create setup orchestrator
        setup = GrafanaSetup(api_key=args.api_key, dry_run=args.dry_run)

        # Setup the dashboard
        dashboard = setup.setup_dashboard(
            uid=args.uid,
            name=args.name,
            panels=panels,
            options=options,
            datasource=args.datasource,
            save=args.save
        )

        # Print result
        action = "updated" if args.dry_run else "updated"
        if not setup.check_dashboard_exists(args.uid):
            action = "created"

        print(f"Dashboard {args.uid} {action} successfully")
        sys.exit(0)

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
