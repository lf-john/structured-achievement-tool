import os
import re
import json # Added for json.dumps
from typing import Dict, Any, Optional

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "templates") # Assuming templates are in project root /templates

def load_template(template_name: str, template_dir: Optional[str] = None) -> str:
    """Placeholder function to load a prompt template."""
    # In a real scenario, this would load from a file
    return f"Template content for {template_name} (placeholder)."

def substitute_placeholders(template: str, substitutions: Dict[str, Any]) -> str:
    """Placeholder function to substitute placeholders in a template."""
    for key, value in substitutions.items():
        template = template.replace(f"{{\1}}", str(value)) # This should replace {{KEY}}
    return template

class PromptBuilder:
    def build_lead_scoring_prompt(self, contact_record: dict) -> str:
        # Placeholder for prompt building logic
        return ""

def build_prompt(
    story: dict,
    phase: str,
    working_directory: str,
    context: dict = None,
    template_dir: Optional[str] = None,
) -> str:
    """Placeholder function to build a prompt for an agent."""
    # This is a very basic placeholder implementation to satisfy BaseAgent's import
    # The real logic would involve loading phase-specific templates and substituting values
    prompt_template = load_template(f"agent_{phase}.md", template_dir)
    substitutions = {
        "STORY_ID": story.get("id", ""),
        "STORY_TITLE": story.get("title", ""),
        "STORY_DESCRIPTION": story.get("description", ""),
        "WORKING_DIRECTORY": working_directory,
        "CONTEXT": json.dumps(context) if context else "",
    }
    return substitute_placeholders(prompt_template, substitutions)
