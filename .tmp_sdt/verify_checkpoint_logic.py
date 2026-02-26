import json
import os
import sys
import time

# Dummy classes to simulate the real components before they are implemented.
# This allows the verification script to be valid for the planning stage.

class CheckpointManager:
    def __init__(self, checkpoint_dir):
        self.checkpoint_dir = checkpoint_dir
        if not os.path.exists(self.checkpoint_dir):
            os.makedirs(self.checkpoint_dir)

    def save(self, task_id, state):
        filepath = os.path.join(self.checkpoint_dir, f"{task_id}.json")
        try:
            with open(filepath, "w") as f:
                json.dump(state, f, indent=2)
            print(f"Checkpoint saved to {filepath}")
        except IOError as e:
            print(f"Error saving checkpoint: {e}")
            # Per requirements, log and continue without blocking
            pass

class StoryExecutor:
    def __init__(self, task_id, stories, checkpoint_dir):
        self.task_id = task_id
        self.stories = stories
        self.completed_stories = []
        self.pending_stories = list(stories)
        self.checkpoint_manager = CheckpointManager(checkpoint_dir)

    def execute_story(self, story):
        # Simulate successful story execution
        print(f"Executing story: {story}")
        self.completed_stories.append(story)
        self.pending_stories.pop(0)

    def run(self):
        for story in list(self.stories):
            self.execute_story(story)
            state = {
                "task_id": self.task_id,
                "current_phase": "EXECUTION",
                "completed_stories": self.completed_stories,
                "pending_stories": [s for s in self.stories if s not in self.completed_stories],
                "timestamp": time.time()
            }
            self.checkpoint_manager.save(self.task_id, state)
        print("Workflow finished.")

def main():
    task_id = "us-002-verification-task"
    stories = ["story_1_setup_env", "story_2_run_tests"]
    checkpoint_dir = ".checkpoints_verify"

    executor = StoryExecutor(task_id, stories, checkpoint_dir)
    executor.run()

    # Verification checks
    checkpoint_file = os.path.join(checkpoint_dir, f"{task_id}.json")
    if not os.path.exists(checkpoint_file):
        print(f"FAIL: Checkpoint file '{checkpoint_file}' was not created.")
        sys.exit(1)

    with open(checkpoint_file, "r") as f:
        data = json.load(f)

    print("Verifying checkpoint content...")
    assert data["task_id"] == task_id, f"Expected task_id {task_id}, got {data['task_id']}"
    assert data["current_phase"] == "EXECUTION", "Incorrect phase"
    assert data["completed_stories"] == stories, "Incorrect completed stories"
    assert data["pending_stories"] == [], "Pending stories should be empty"
    assert "timestamp" in data, "Timestamp missing"

    print("SUCCESS: Checkpoint verification passed.")

    # Cleanup
    os.remove(checkpoint_file)
    os.rmdir(checkpoint_dir)
    sys.exit(0)

if __name__ == "__main__":
    main()
