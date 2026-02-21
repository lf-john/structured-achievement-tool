import os
import sys
import json
from src.orchestrator import Orchestrator

def run_demo():
    # Configuration (Mocks used in this environment)
    PROJECT_PATH = os.path.expanduser("~/projects/ralph-pro-python")
    API_KEY = "fake-key" # Mocks don't need real keys
    
    orch = Orchestrator(project_path=PROJECT_PATH, api_key=API_KEY)
    
    test_tasks_dir = os.path.join(PROJECT_PATH, "test_tasks")
    os.makedirs(test_tasks_dir, exist_ok=True)
    
    # Define tasks
    tasks = {
        "research": "Summarize the current project architecture.",
        "config": "Create a basic docker-compose.yml for a web app.",
        "development": "Implement a sum function in Python."
    }
    
    for name, request in tasks.items():
        task_dir = os.path.join(test_tasks_dir, f"task-{name}")
        os.makedirs(task_dir, exist_ok=True)
        task_file = os.path.join(task_dir, "001.md")
        
        with open(task_file, "w") as f:
            f.write(request)
            
        print(f"--- Processing {name} task ---")
        try:
            # Note: This will attempt to call the CLI tools. 
            # In this environment, we rely on the unit tests for reliability.
            # Here we just print the classification and PRD to show logic.
            
            classification = orch.agent.classify(request)
            print(f"Classification: {classification['task_type']} ({classification['confidence']})")
            
            prd = orch.agent.decompose(request, classification['task_type'])
            print(f"Decomposed into {len(prd['stories'])} stories.")
            for s in prd['stories']:
                print(f"  - {s['id']}: {s['title']} (Type: {s.get('type', 'dev')})")
                
        except Exception as e:
            print(f"Error processing {name}: {str(e)}")
        print("
")

if __name__ == "__main__":
    run_demo()
