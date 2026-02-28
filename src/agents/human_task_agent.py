"""
Human Task Agent — Detect human-required actions and generate step-by-step instructions.

When a story requires human intervention (credentials, API keys, external UI
configuration, DNS changes, etc.), this agent:
1. Determines whether human input is needed
2. Generates detailed click-by-click instructions
3. Returns a HumanTaskResponse with instructions, required inputs, and context

Complexity: 5 (Analyst). Uses the LLM to analyze the story description and
produce structured guidance for the human operator.
"""

import logging
from typing import Type, List, Optional

from pydantic import BaseModel, Field

from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


# --- Pydantic Response Models ---

class RequiredInput(BaseModel):
    """A single piece of information the human must provide."""
    name: str = Field(description="Short identifier, e.g. 'aws_access_key'")
    description: str = Field(description="What this input is and where to find it")
    example: str = Field(default="", description="Example value (redacted if sensitive)")
    sensitive: bool = Field(default=False, description="Whether this is a secret/credential")


class VerificationCheck(BaseModel):
    """A verification check for human task TDD."""
    type: str = Field(description="Check type: command, http, dns, port_check, file_check, service_check, config_check")
    description: str = Field(default="", description="What this check verifies")
    command: str = Field(default="", description="Shell command (for command type)")
    url: str = Field(default="", description="URL (for http type)")
    hostname: str = Field(default="", description="Hostname (for dns type)")
    expected_value: str = Field(default="", description="Expected value")
    expected_status: int = Field(default=200, description="Expected HTTP status")
    wait_seconds: int = Field(default=0, description="Seconds to wait before checking (0 = immediate)")
    max_attempts: int = Field(default=1, description="Max retry attempts (1 = no retry)")
    is_quick_check: bool = Field(default=True, description="True for immediate checks, False for delayed/final checks")


class HumanTaskResponse(BaseModel):
    """Response from the Human Task Agent."""
    needs_human: bool = Field(
        description="Whether this story requires human intervention"
    )
    reason: str = Field(
        default="",
        description="Why human intervention is needed (or why it is not)"
    )
    instructions: str = Field(
        default="",
        description="Step-by-step instructions for the human operator"
    )
    required_inputs: List[RequiredInput] = Field(
        default_factory=list,
        description="List of inputs the human must provide"
    )
    provider: str = Field(
        default="",
        description="External service provider, e.g. 'AWS', 'Cloudflare', 'GitHub'"
    )
    documentation_url: str = Field(
        default="",
        description="URL to relevant documentation for the human task"
    )
    estimated_time_minutes: int = Field(
        default=0,
        description="Estimated time for the human to complete the task"
    )
    verification_checks: List[VerificationCheck] = Field(
        default_factory=list,
        description="TDD-style verification checks: quick checks (immediate) and final checks (delayed)"
    )


# --- Detection heuristics (no LLM needed) ---

# Keywords that strongly indicate human intervention is required
HUMAN_KEYWORDS = {
    # Credentials and secrets
    "api key", "api_key", "apikey", "secret key", "secret_key",
    "access key", "access_key", "credentials", "password", "token",
    "oauth", "client_id", "client_secret", "private key",
    # External UI / console actions
    "console", "dashboard", "portal", "admin panel", "web ui",
    "control panel", "management console",
    # DNS and domain
    "dns record", "dns configuration", "domain verification",
    "cname", "mx record", "txt record", "a record", "aaaa record",
    "nameserver", "registrar",
    # Cloud provider setup
    "aws ses", "ses verification", "ses sandbox",
    "cloudflare", "route53", "google cloud console",
    "azure portal", "digitalocean",
    # Manual configuration
    "manual configuration", "manual setup", "manually configure",
    "sign up", "register", "create account", "enable service",
    "activate", "verify domain", "verify email",
    # Billing and subscriptions
    "billing", "subscription", "payment method", "pricing tier",
    "upgrade plan",
}

# Story types that are inherently human tasks
HUMAN_STORY_TYPES = {"assignment", "approval", "qa_feedback", "escalation"}

# Provider detection patterns (keyword -> provider name)
PROVIDER_PATTERNS = {
    "aws": "AWS",
    "amazon": "AWS",
    "ses": "AWS SES",
    "route53": "AWS Route53",
    "cloudflare": "Cloudflare",
    "google cloud": "Google Cloud",
    "gcp": "Google Cloud",
    "azure": "Microsoft Azure",
    "digitalocean": "DigitalOcean",
    "github": "GitHub",
    "gitlab": "GitLab",
    "docker hub": "Docker Hub",
    "npm": "npm",
    "pypi": "PyPI",
    "sendgrid": "SendGrid",
    "mailgun": "Mailgun",
    "twilio": "Twilio",
    "stripe": "Stripe",
    "slack": "Slack",
    "discord": "Discord",
    "mautic": "Mautic",
    "suitecrm": "SuiteCRM",
    "n8n": "N8N",
}


def detect_human_needs(story: dict) -> bool:
    """Fast heuristic check: does this story likely need human intervention?

    Checks story type, title, and description against known patterns.
    This is a cheap pre-filter before invoking the LLM for detailed analysis.
    """
    story_type = story.get("type", "development")
    if story_type in HUMAN_STORY_TYPES:
        return True

    # Check title and description for human keywords
    text = (
        story.get("title", "") + " " + story.get("description", "")
    ).lower()

    for keyword in HUMAN_KEYWORDS:
        if keyword in text:
            return True

    return False


def detect_provider(story: dict) -> str:
    """Detect the external service provider from story text."""
    text = (
        story.get("title", "") + " " + story.get("description", "")
    ).lower()

    for pattern, provider in PROVIDER_PATTERNS.items():
        if pattern in text:
            return provider

    return ""


class HumanTaskAgent(BaseAgent):
    """Agent that analyzes stories for human intervention needs.

    Two modes of operation:
    1. Fast path (detect_human_needs): keyword-based heuristic, no LLM call
    2. Full analysis (analyze): LLM-powered detailed instruction generation

    The fast path is used as a pre-filter in story_executor. If it triggers,
    the full LLM analysis generates step-by-step instructions.
    """

    @property
    def agent_name(self) -> str:
        return "human_task_analyst"

    @property
    def response_model(self) -> Type[BaseModel]:
        return HumanTaskResponse

    async def analyze(
        self,
        story: dict,
        working_directory: str,
        task_description: str = "",
    ) -> HumanTaskResponse:
        """Analyze a story and generate human task instructions if needed.

        This is the full LLM-powered analysis. Call detect_human_needs() first
        as a cheap pre-filter.

        Args:
            story: Story dict from decomposition
            working_directory: Project working directory
            task_description: Original user request for additional context

        Returns:
            HumanTaskResponse with needs_human flag and instructions
        """
        # Build context for the LLM
        context = {
            "task_description": task_description,
            "detected_provider": detect_provider(story),
        }

        analysis_story = {
            "id": story.get("id", "HUMAN_ANALYSIS"),
            "title": story.get("title", "Human Task Analysis"),
            "description": story.get("description", ""),
        }

        try:
            result = await self.execute(
                story=analysis_story,
                phase="HUMAN_TASK_ANALYSIS",
                working_directory=working_directory,
                context=context,
                template_dir=None,
            )
            return result

        except Exception as e:
            logger.warning(
                f"HumanTaskAgent LLM analysis failed: {e}. "
                f"Falling back to heuristic detection."
            )
            # Fallback: use heuristics to build a basic response
            return self._heuristic_response(story)

    def _heuristic_response(self, story: dict) -> HumanTaskResponse:
        """Build a basic HumanTaskResponse from heuristics when LLM fails."""
        needs = detect_human_needs(story)
        provider = detect_provider(story)

        if not needs:
            return HumanTaskResponse(
                needs_human=False,
                reason="No human intervention indicators detected.",
            )

        # Build basic instructions from the story description
        description = story.get("description", "")
        title = story.get("title", "Unknown Task")
        criteria = story.get("acceptanceCriteria", [])

        instructions_parts = [
            f"# Human Action Required: {title}\n",
            f"## What You Need To Do\n",
            f"{description}\n",
        ]

        if provider:
            instructions_parts.append(f"## Provider: {provider}\n")

        if criteria:
            instructions_parts.append("## Verification Steps\n")
            for i, criterion in enumerate(criteria, 1):
                instructions_parts.append(f"{i}. {criterion}")
            instructions_parts.append("")

        instructions_parts.append(
            "## When Complete\n"
            "Provide the requested information or confirmation in your response, "
            "then remove the `#` from `# <Pending>` to signal completion.\n"
        )

        return HumanTaskResponse(
            needs_human=True,
            reason=f"Story requires human action: {title}",
            instructions="\n".join(instructions_parts),
            provider=provider,
        )
