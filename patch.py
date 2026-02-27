import os
import re

with open('src/execution/story_executor.py', 'r') as f:
    code = f.read()

replacement1 = """    from langgraph.checkpoint.sqlite import SqliteSaver
    import os
    db_path = os.path.join(working_directory, ".memory", "checkpoints.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    with SqliteSaver.from_conn_string(db_path) as checkpointer:
        # Get compiled workflow
        graph = get_workflow_for_story(story, re, notifier=notifier, checkpointer=checkpointer)
"""

code = code.replace("    # Get compiled workflow\n    graph = get_workflow_for_story(story, re, notifier=notifier)\n", replacement1)

# Now we need to indent everything from `    # Capture base commit for reset on retry` down to the end of the `with` block!
# Actually, the entire rest of the `execute_story` function needs to be indented by 4 spaces.
lines = code.split('\n')
out_lines = []
in_with_block = False

for i, line in enumerate(lines):
    if line.strip() == "# Capture base commit for reset on retry":
        in_with_block = True

    if in_with_block:
        if line == "":
            out_lines.append(line)
        else:
            out_lines.append("    " + line)
    else:
        out_lines.append(line)

# Now, we also need to update the `graph.invoke` call
# Inside the new indented block, we find `state = create_initial_state(...)` and `graph.invoke(state)`
# and replace them with the resume logic.
code = '\n'.join(out_lines)

resume_logic_old = """        # Create initial state
        state = create_initial_state(
            story=story,
            task_id=task_id,
            task_description=task_description,
            working_directory=working_directory,
            max_attempts=max_attempts,
            mediator_enabled=mediator_enabled,
        )
        state["story_attempt"] = attempt
        state["failure_context"] = last_failure_reason if attempt > 1 else ""

        # Execute the workflow
        try:
            final_state = graph.invoke(state)"""

resume_logic_new = """        config = {
            "configurable": {
                "thread_id": f"{story_id}_attempt_{attempt}",
                "task_id": task_id,
            }
        }

        # Check if we should resume
        state_to_invoke = None
        checkpoint_state = graph.get_state(config)
        if not checkpoint_state.values:
            # Create initial state for fresh run
            state_to_invoke = create_initial_state(
                story=story,
                task_id=task_id,
                task_description=task_description,
                working_directory=working_directory,
                max_attempts=max_attempts,
                mediator_enabled=mediator_enabled,
            )
            state_to_invoke["story_attempt"] = attempt
            state_to_invoke["failure_context"] = last_failure_reason if attempt > 1 else ""

        # Execute the workflow
        try:
            final_state = graph.invoke(state_to_invoke, config=config)"""

# Note that because we indented everything, the old logic string needs to have 4 extra spaces
resume_logic_old_indented = resume_logic_old.replace("\n", "\n    ")
resume_logic_new_indented = resume_logic_new.replace("\n", "\n    ")

code = code.replace(resume_logic_old_indented, resume_logic_new_indented)

with open('src/execution/story_executor.py', 'w') as f:
    f.write(code)
