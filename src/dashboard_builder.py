"""
Dashboard builder module for creating Grafana dashboard structures and panel configurations.

This module provides the DashboardBuilder class for constructing valid Grafana dashboards
with panel utilities for different panel types (time series, stat, gauge, pie chart, heatmap)
and Prometheus datasource configuration.
"""


class DashboardBuilder:
    """Builder class for creating Grafana dashboards and panels."""

    def create_dashboard(self, name, uid, panels, options):
        """
        Create a base Grafana dashboard structure.

        Args:
            name: Dashboard name
            uid: Dashboard unique identifier
            panels: List of panel objects
            options: Dictionary of custom options to override defaults

        Returns:
            Dictionary representing a valid Grafana dashboard
        """
        if options is None:
            options = {}

        # Build base dashboard structure
        dashboard = {
            'type': 'dashboard',
            'title': name,
            'name': name,
            'uid': uid,
            'time': {'from': 'now-6h', 'to': 'now'},
            'refresh': '30s',
            'panels': panels if panels else [],
            'templating': {
                'list': [
                    {
                        'name': 'time_range',
                        'type': 'interval',
                        'current': {'value': '30s', 'text': '30s'},
                        'options': [
                            {'value': '5s', 'text': '5s'},
                            {'value': '30s', 'text': '30s'},
                            {'value': '1m', 'text': '1m'},
                            {'value': '5m', 'text': '5m'},
                            {'value': '10m', 'text': '10m'},
                        ]
                    }
                ]
            }
        }

        # Override defaults with provided options
        if 'time' in options:
            dashboard['time'] = options['time']
        if 'refresh' in options:
            dashboard['refresh'] = options['refresh']

        # Apply any other custom options that aren't time or refresh
        for key, value in options.items():
            if key not in ['time', 'refresh']:
                dashboard[key] = value

        return dashboard

    def create_time_series_panel(self, title, queries, options):
        """
        Create a time series panel.

        Args:
            title: Panel title
            queries: List of query objects
            options: Dictionary of panel options

        Returns:
            Dictionary representing a time series panel
        """
        if options is None:
            options = {}

        panel = {
            'type': 'timeseries',
            'title': title,
            'targets': queries if queries else []
        }

        # Apply options
        for key, value in options.items():
            panel[key] = value

        return panel

    def create_stat_panel(self, title, queries, options):
        """
        Create a stat panel.

        Args:
            title: Panel title
            queries: List of query objects
            options: Dictionary of panel options

        Returns:
            Dictionary representing a stat panel
        """
        if options is None:
            options = {}

        panel = {
            'type': 'stat',
            'title': title,
            'targets': queries if queries else []
        }

        # Apply options
        for key, value in options.items():
            panel[key] = value

        return panel

    def create_gauge_panel(self, title, queries, options):
        """
        Create a gauge panel.

        Args:
            title: Panel title
            queries: List of query objects
            options: Dictionary of panel options

        Returns:
            Dictionary representing a gauge panel
        """
        if options is None:
            options = {}

        panel = {
            'type': 'gauge',
            'title': title,
            'targets': queries if queries else []
        }

        # Handle gauge-specific options
        if options:
            gauge_options = {}
            for key, value in options.items():
                if key in ['min', 'max', 'value']:
                    gauge_options[key] = value
            if gauge_options:
                panel['options'] = gauge_options

            # Apply other options directly to panel
            for key, value in options.items():
                if key not in ['min', 'max', 'value']:
                    panel[key] = value

        return panel

    def create_pie_chart_panel(self, title, queries, options):
        """
        Create a pie chart panel.

        Args:
            title: Panel title
            queries: List of query objects
            options: Dictionary of panel options

        Returns:
            Dictionary representing a pie chart panel
        """
        if options is None:
            options = {}

        panel = {
            'type': 'piechart',
            'title': title,
            'targets': queries if queries else []
        }

        # Handle pie chart-specific options
        if options:
            pie_options = {}
            for key, value in options.items():
                if key in ['orientation']:
                    pie_options[key] = value
            if pie_options:
                panel['options'] = pie_options

            # Apply other options directly to panel
            for key, value in options.items():
                if key not in ['orientation']:
                    panel[key] = value

        return panel

    def create_heatmap_panel(self, title, queries, options):
        """
        Create a heatmap panel.

        Args:
            title: Panel title
            queries: List of query objects
            options: Dictionary of panel options

        Returns:
            Dictionary representing a heatmap panel
        """
        if options is None:
            options = {}

        panel = {
            'type': 'heatmap',
            'title': title,
            'targets': queries if queries else []
        }

        # Apply options
        for key, value in options.items():
            panel[key] = value

        return panel

    def create_prometheus_datasource(self, name, url, access="proxy", version=None):
        """
        Create a Prometheus datasource configuration.

        Args:
            name: Datasource name
            url: Prometheus server URL
            access: Access mode ('proxy' or 'direct'). Defaults to 'proxy'.
            version: Optional Prometheus version number

        Returns:
            Dictionary representing a Prometheus datasource configuration
        """
        datasource = {
            'name': name,
            'type': 'prometheus',
            'url': url,
            'access': access
        }

        if version is not None:
            datasource['version'] = version

        return datasource
