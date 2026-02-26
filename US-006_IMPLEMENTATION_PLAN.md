
```json
{
  "designPlan": {
    "architectureAnalysis": {
      "filesToCreate": [
        "tests/test_us_006_provider_usage_panel.py"
      ],
      "filesToModify": [
        "src/dashboard_builder.py"
      ],
      "dependencies": [
        "This story relies on the existing `DashboardBuilder` class structure in `src/dashboard_builder.py`. No new external dependencies are required."
      ]
    },
    "implementationPlan": [
      {
        "filePath": "src/dashboard_builder.py",
        "purpose": "To add a new function to the DashboardBuilder class that constructs a Grafana pie chart panel specifically for visualizing the `sat_provider_requests_total` metric.",
        "keyChanges": [
          "Add a new method `create_provider_usage_panel(self, custom_title=None, grid_pos=None, datasource=None)` to the `DashboardBuilder` class.",
          "This method will generate a dictionary representing the JSON for a Grafana pie chart panel.",
          "The panel's query will be configured to target the `sat_provider_requests_total` metric, summed by the `provider` label."
        ],
        "dataFlow": "The method will be called by a higher-level script responsible for generating the complete dashboard. It will accept configuration options (title, position) and return a JSON object for the new panel, which will then be added to the main dashboard's list of panels.",
        "interfaces": [
          "def create_provider_usage_panel(self, custom_title: str = None, grid_pos: dict = None, datasource: str = None) -> dict:"
        ]
      },
      {
        "filePath": "tests/test_us_006_provider_usage_panel.py",
        "purpose": "To provide comprehensive, TDD-style unit tests for the new `create_provider_usage_panel` method, ensuring its correctness and adherence to the required Grafana JSON format.",
        "keyChanges": [
          "Create a new test class `TestCreateProviderUsagePanel`.",
          "Add test cases to verify the panel's title, type (`piechart`), datasource, grid position, and the correctness of the Prometheus query.",
          "Ensure the generated JSON structure is valid and contains all necessary fields for a Grafana pie chart."
        ],
        "dataFlow": "The test methods will call `DashboardBuilder.create_provider_usage_panel` with various arguments and then assert that the returned dictionary matches the expected structure and values.",
        "interfaces": [
          "N/A (Test module)"
        ]
      }
    ],
    "acceptanceCriteriaMapping": [
      {
        "criterion": "Pie chart panel created with correct title",
        "implementationSteps": [
          "The `create_provider_usage_panel` method will set the 'title' key in the panel's JSON to 'Provider Usage Breakdown' by default, or to the `custom_title` if provided."
        ],
        "verificationMethod": "A unit test in `tests/test_us_006_provider_usage_panel.py` will assert that the `title` field in the generated dictionary is correct."
      },
      {
        "criterion": "Includes sat_provider_requests_total metric",
        "implementationSteps": [
          "The method will create a 'targets' array in the JSON, with a dictionary containing an 'expr' key set to 'sum by (provider) (sat_provider_requests_total)'."
        ],
        "verificationMethod": "A unit test will assert that `panel['targets'][0]['expr']` equals the specified query string."
      },
      {
        "criterion": "Grouped by 'provider' label",
        "implementationSteps": [
          "The `sum by (provider)` clause in the Prometheus query handles the grouping.",
          "The legend format will be set to `{{provider}}` to display the label values."
        ],
        "verificationMethod": "The unit test for the query (`expr`) will implicitly verify this. An additional check for the legend format will be added."
      },
      {
        "criterion": "Proper pie chart formatting",
        "implementationSteps": [
          "The method will set the 'type' key in the panel's JSON to 'piechart'.",
          "It will include standard pie chart options, such as setting `pieType` to `donut`."
        ],
        "verificationMethod": "A unit test will assert that `panel['type']` is 'piechart' and that `panel['options']['pieType']` is 'donut'."
      },
      {
        "criterion": "Panel JSON is valid Grafana format",
        "implementationSteps": [
          "The `create_provider_usage_panel` function will construct a dictionary that includes all required fields for a panel, such as `id`, `title`, `type`, `targets`, and `gridPos`."
        ],
        "verificationMethod": "Unit tests will verify the presence and correct types of all essential keys in the generated panel JSON."
      }
    ],
    "edgeCasesAndRisks": {
      "boundaryConditions": [
        "The function should handle cases where optional arguments like `custom_title`, `grid_pos`, and `datasource` are not provided, applying sensible defaults."
      ],
      "errorScenarios": [
        "If the `sat_provider_requests_total` metric does not exist or has no data in Prometheus, the panel will render correctly with a 'No data' message in Grafana. This is acceptable behavior and requires no special handling in the builder."
      ],
      "securityConsiderations": [
        "There are no security considerations for this story, as it involves generating configuration JSON and does not handle user input or sensitive data."
      ],
      "performanceImplications": [
        "There are no performance implications. The JSON generation is a lightweight, instantaneous operation."
      ]
    },
    "implementationOrder": [
      "Create the test file `tests/test_us_006_provider_usage_panel.py` and write an initial, failing test case for the `create_provider_usage_panel` method.",
      "Modify `src/dashboard_builder.py` to add the `create_provider_usage_panel` method and implement its basic functionality to make the initial test pass.",
      "Expand the test suite in `tests/test_us_006_provider_usage_panel.py` to cover all acceptance criteria, including optional parameters and formatting options.",
      "Refine the implementation of `create_provider_usage_panel` until all tests pass.",
      "Finally, a separate step (outside this story's scope) would be to integrate this new panel into the main dashboard generation script and deploy it."
    ]
  }
}
```
<promise>COMPLETE</promise>
