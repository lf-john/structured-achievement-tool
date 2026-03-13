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
            "type": "dashboard",
            "title": name,
            "name": name,
            "uid": uid,
            "time": {"from": "now-6h", "to": "now"},
            "refresh": "30s",
            "panels": panels if panels else [],
            "templating": {
                "list": [
                    {
                        "name": "time_range",
                        "type": "interval",
                        "current": {"value": "30s", "text": "30s"},
                        "options": [
                            {"value": "5s", "text": "5s"},
                            {"value": "30s", "text": "30s"},
                            {"value": "1m", "text": "1m"},
                            {"value": "5m", "text": "5m"},
                            {"value": "10m", "text": "10m"},
                        ],
                    }
                ]
            },
        }

        # Override defaults with provided options
        if "time" in options:
            dashboard["time"] = options["time"]
        if "refresh" in options:
            dashboard["refresh"] = options["refresh"]

        # Apply any other custom options that aren't time or refresh
        for key, value in options.items():
            if key not in ["time", "refresh"]:
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

        panel = {"type": "timeseries", "title": title, "targets": queries if queries else []}

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

        panel = {"type": "stat", "title": title, "targets": queries if queries else []}

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

        panel = {"type": "gauge", "title": title, "targets": queries if queries else []}

        # Handle gauge-specific options
        if options:
            gauge_options = {}
            for key, value in options.items():
                if key in ["min", "max", "value"]:
                    gauge_options[key] = value
            if gauge_options:
                panel["options"] = gauge_options

            # Apply other options directly to panel
            for key, value in options.items():
                if key not in ["min", "max", "value"]:
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

        panel = {"type": "piechart", "title": title, "targets": queries if queries else []}

        # Handle pie chart-specific options
        if options:
            pie_options = {}
            for key, value in options.items():
                if key in ["orientation"]:
                    pie_options[key] = value
            if pie_options:
                panel["options"] = pie_options

            # Apply other options directly to panel
            for key, value in options.items():
                if key not in ["orientation"]:
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

        panel = {"type": "heatmap", "title": title, "targets": queries if queries else []}

        # Apply options
        for key, value in options.items():
            panel[key] = value

        return panel

    def create_queue_depth_panel(
        self, custom_title=None, min=None, max=None, grid_pos=None, datasource=None, queries=None
    ):
        """
        Create a gauge panel showing sat_queue_depth metric.

        Args:
            custom_title: Custom title for the panel (defaults to 'Queue Depth')
            min: Minimum value for the gauge (optional)
            max: Maximum value for the gauge (optional)
            grid_pos: Grid position {'x': int, 'y': int, 'w': int, 'h': int}
            datasource: Grafana datasource name (defaults to 'Prometheus')
            queries: List of target queries (optional, defaults to queue depth metric)

        Returns:
            Dictionary representing a Grafana gauge panel
        """
        if queries is None:
            queries = [{"expr": "sat_queue_depth", "legendFormat": "queue_depth"}]

        panel = {"type": "gauge", "title": custom_title if custom_title else "Queue Depth", "targets": queries}

        # Apply optional parameters
        if grid_pos is not None:
            panel["gridPos"] = grid_pos
        if datasource is not None:
            panel["datasource"] = datasource

        # Add fieldConfig with thresholds for color coding
        panel["fieldConfig"] = {
            "defaults": {
                "thresholds": {
                    "mode": "absolute",
                    "steps": [
                        {"value": 0, "color": "green"},
                        {"value": 10, "color": "yellow"},
                        {"value": 50, "color": "orange"},
                        {"value": 100, "color": "red"},
                    ],
                }
            }
        }

        # Always add options for gauge formatting
        panel["options"] = {}

        # Apply min/max values if provided
        if min is not None:
            panel["options"]["min"] = min
        if max is not None:
            panel["options"]["max"] = max

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
        datasource = {"name": name, "type": "prometheus", "url": url, "access": access}

        if version is not None:
            datasource["version"] = version

        return datasource

    def create_task_completion_panel(
        self,
        custom_title=None,
        grid_pos=None,
        datasource=None,
        yaxis_min=None,
        yaxis_max=None,
        time_range=None,
        queries=None,
        legends=None,
    ):
        """
        Create a stat panel showing Task Completion count metric.

        Args:
            custom_title: Custom title for the panel (defaults to 'Task Completion Count')
            grid_pos: Grid position {'x': int, 'y': int, 'w': int, 'h': int}
            datasource: Grafana datasource name (defaults to 'Prometheus')
            yaxis_min: Minimum y-axis value (optional)
            yaxis_max: Maximum y-axis value (optional)
            time_range: Time range {'from': str, 'to': str}
            queries: List of target queries (optional, defaults to completed metric)
            legends: List of legend labels (optional, defaults to 'Completed')

        Returns:
            Dictionary representing a Grafana stat panel
        """
        if queries is None:
            queries = [{"expr": "sat_tasks_completed_total", "legendFormat": "Completed"}]

        panel = {"type": "stat", "title": custom_title if custom_title else "Task Completion Count", "targets": queries}

        # Apply optional parameters
        if grid_pos is not None:
            panel["gridPos"] = grid_pos
        if datasource is not None:
            panel["datasource"] = datasource
        if yaxis_min is not None:
            panel["yaxis"] = panel.get("yaxis", {})
            panel["yaxis"]["min"] = yaxis_min
        if yaxis_max is not None:
            panel["yaxis"] = panel.get("yaxis", {})
            panel["yaxis"]["max"] = yaxis_max
        if time_range is not None:
            panel["timeRange"] = time_range

        # Add fieldConfig and options for proper Grafana stat formatting
        panel["fieldConfig"] = {
            "defaults": {
                "custom": {"displayMode": "color-background", "colorMode": "value"},
                "color": {"mode": "thresholds"},
                "thresholds": {
                    "mode": "absolute",
                    "steps": [
                        {"value": 0, "color": "gray"},
                        {"value": 100, "color": "green"},
                        {"value": 500, "color": "yellow"},
                        {"value": 1000, "color": "orange"},
                        {"value": 5000, "color": "red"},
                    ],
                },
            }
        }

        panel["options"] = {"graphMode": "none", "reduceOptions": {"values": False, "calcs": ["lastNotNull"]}}

        return panel

    def create_stories_success_fail_panel(
        self,
        custom_title=None,
        grid_pos=None,
        datasource=None,
        yaxis_min=None,
        yaxis_max=None,
        time_range=None,
        queries=None,
    ):
        """
        Create a time series panel showing Stories Success/Fail Rate metrics.

        Args:
            custom_title: Custom title for the panel (defaults to 'Stories Success/Fail Rate')
            grid_pos: Grid position {'x': int, 'y': int, 'w': int, 'h': int}
            datasource: Grafana datasource name (defaults to 'Prometheus')
            yaxis_min: Minimum y-axis value (optional)
            yaxis_max: Maximum y-axis value (optional)
            time_range: Time range {'from': str, 'to': str}
            queries: List of target queries (optional, defaults to succeeded/failed metrics)

        Returns:
            Dictionary representing a Grafana time series panel
        """
        if queries is None:
            queries = [
                {"expr": "sat_stories_succeeded_total", "legendFormat": "Succeeded"},
                {"expr": "sat_stories_failed_total", "legendFormat": "Failed"},
            ]

        panel = {
            "type": "timeseries",
            "title": custom_title if custom_title else "Stories Success/Fail Rate",
            "targets": queries,
        }

        # Apply optional parameters
        if grid_pos is not None:
            panel["gridPos"] = grid_pos
        if datasource is not None:
            panel["datasource"] = datasource
        if yaxis_min is not None:
            panel["yaxis"] = panel.get("yaxis", {})
            panel["yaxis"]["min"] = yaxis_min
        if yaxis_max is not None:
            panel["yaxis"] = panel.get("yaxis", {})
            panel["yaxis"]["max"] = yaxis_max
        if time_range is not None:
            panel["timeRange"] = time_range

        # Add fieldConfig and options for proper Grafana formatting
        panel["fieldConfig"] = {
            "defaults": {
                "custom": {"lineWidth": 2, "pointRadius": 4, "fillOpacity": 20},
                "color": {"mode": "palette-classic"},
                "thresholds": {
                    "mode": "absolute",
                    "steps": [{"value": 0, "color": "green"}, {"value": 1, "color": "yellow"}],
                },
            }
        }

        panel["options"] = {
            "legend": {"displayMode": "list", "placement": "bottom"},
            "tooltip": {"mode": "multi", "sort": "none"},
        }

        return panel

    def create_provider_usage_panel(self, custom_title=None, grid_pos=None, datasource=None, queries=None):
        """
        Create a pie chart panel showing Provider Usage Breakdown metric.

        Args:
            custom_title: Custom title for the panel (defaults to 'Provider Usage Breakdown')
            grid_pos: Grid position {'x': int, 'y': int, 'w': int, 'h': int}
            datasource: Grafana datasource name (defaults to 'Prometheus')
            queries: List of target queries (optional, defaults to provider usage metric)

        Returns:
            Dictionary representing a Grafana pie chart panel
        """
        if queries is None:
            queries = [{"expr": "sum by (provider) (sat_provider_requests_total)", "legendFormat": "{{provider}}"}]

        panel = {
            "type": "piechart",
            "title": custom_title if custom_title else "Provider Usage Breakdown",
            "targets": queries,
        }

        # Apply optional parameters
        if grid_pos is not None:
            panel["gridPos"] = grid_pos
        if datasource is not None:
            panel["datasource"] = datasource

        # Add fieldConfig and options for proper Grafana pie chart formatting
        panel["fieldConfig"] = {
            "defaults": {
                "color": {"mode": "palette-classic"},
                "custom": {"displayMode": "percent", "pieType": "donut", "showLegend": True},
            }
        }

        panel["options"] = {
            "legend": {"displayMode": "list", "placement": "bottom"},
            "tooltip": {"mode": "single", "sort": "none"},
        }

        return panel

    def create_response_time_histogram_panel(self, custom_title=None, grid_pos=None, datasource=None, queries=None):
        """
        Create a heatmap panel displaying sat_response_time_seconds_bucket metric.

        Args:
            custom_title: Custom title for the panel (defaults to 'Response Time Histogram')
            grid_pos: Grid position {'x': int, 'y': int, 'w': int, 'h': int}
            datasource: Grafana datasource name (defaults to 'Prometheus')
            queries: List of target queries (optional, defaults to response time histogram metric)

        Returns:
            Dictionary representing a Grafana heatmap panel
        """
        if queries is None:
            queries = [{"expr": "sat_response_time_seconds_bucket", "legendFormat": "{{le}}"}]

        panel = {
            "type": "heatmap",
            "title": custom_title if custom_title else "Response Time Histogram",
            "targets": queries,
        }

        # Apply optional parameters
        if grid_pos is not None:
            panel["gridPos"] = grid_pos
        if datasource is not None:
            panel["datasource"] = datasource

        # Add fieldConfig for heatmap formatting
        panel["fieldConfig"] = {
            "defaults": {
                "custom": {"scaleDistribution": {"type": "linear"}},
                "color": {"scheme": "Spectral"},
                "mappings": [],
            }
        }

        # Add options for heatmap visualization
        panel["options"] = {
            "calculate": False,
            "color": {"scale": {"mode": "scheme", "scheme": "Spectral"}},
            "dataFormat": "timeseries",
            "dimensions": {
                "x": {"field": "time"},
                "y": {"field": "le", "displayMode": "legend"},
                "z": {"field": "value", "displayMode": "color"},
            },
            "tooltip": {"mode": "single", "sort": "none"},
            "yAxis": {"unit": "s"},
        }

        return panel
