with open('src/execution/story_executor.py', 'r') as f:
    lines = f.readlines()

out = []
i = 0
while i < len(lines):
    line = lines[i]
    if line.strip() == "# Create initial state":
        out.extend([
            "            config = {\n",
            "                \"configurable\": {\n",
            "                    \"thread_id\": f\"{story_id}_attempt_{attempt}\",\n",
            "                    \"task_id\": task_id,\n",
            "                }\n",
            "            }\n\n",
            "            # Check if we should resume\n",
            "            state_to_invoke = None\n",
            "            checkpoint_state = graph.get_state(config)\n",
            "            if not checkpoint_state.values:\n",
            "                # Create initial state for fresh run\n",
            "                state_to_invoke = create_initial_state(\n",
            "                    story=story,\n",
            "                    task_id=task_id,\n",
            "                    task_description=task_description,\n",
            "                    working_directory=working_directory,\n",
            "                    max_attempts=max_attempts,\n",
            "                    mediator_enabled=mediator_enabled,\n",
            "                )\n",
            "                state_to_invoke[\"story_attempt\"] = attempt\n",
            "                state_to_invoke[\"failure_context\"] = last_failure_reason if attempt > 1 else \"\"\n\n"
        ])
        while "final_state = graph.invoke(state)" not in lines[i]:
            i += 1
        out.append("            try:\n")
        out.append("                final_state = graph.invoke(state_to_invoke, config=config)\n")
        i += 1
    else:
        out.append(line)
        i += 1

with open('src/execution/story_executor.py', 'w') as f:
    f.writelines(out)
