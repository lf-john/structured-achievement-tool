# VERIFY-SCRIPT Phase: {{STORY_TITLE}}

You are verifying the execution of a configuration or devops task.

## Result of the automated verification script:
{{VERIFICATION_RESULT}}

## Your Task
1. Read the output of the automated verification script.
2. If the script succeeded (exit code 0), review the output and signal completion.
3. If the script failed (exit code non-zero), analyze the failure and provide instructions to fix it.

## Expected Output
Output your response as JSON.

```json
{
  "exitCode": 0,
  "status": "passed|failed",
  "analysis": "Summary of what the verification script checked and the result",
  "fixInstructions": "If failed, specific instructions for what needs to be fixed in the EXECUTE phase"
}
```

## Completion Signal
- If the script succeeded: Output `<promise>COMPLETE</promise>`
- If the script failed: Output `<promise>FAILED</promise>` with an explanation of why and what needs to be fixed in the EXECUTE phase.
