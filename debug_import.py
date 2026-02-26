import sys
sys.path.insert(0, '/home/johnlane/projects/structured-achievement-tool')

try:
    import tests.US_008_llm_cost_dashboard
except ImportError as e:
    print(f"ImportError: {e}")
except Exception as e:
    print(f"Other error: {e}")
